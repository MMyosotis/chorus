"""主调度 agent：流式对话入口，普通对话直接回复，创作请求经建图工具路由。

业务差异进策略，主流程不识工具名与挂起载荷，有活跃创作任务时拒绝新请求。
意图记录与建图均靠 prompt 引导 + 工具内校验，不做代码层强制拦截。
"""
from __future__ import annotations

from typing import Iterator, Optional

from chorus.agents.chat_model import ChatModelProvider
from chorus.agents.loop import AgentLoop, LoopStrategy
from chorus.agents.runtime import AgentContext, LoopAction, LoopSignal
from chorus.config import TOOL_WHITELISTS
from chorus.domain.events import (
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    SseEvent,
    SuspendEvent,
    TraceEvent,
)
from chorus.domain.bypass import BypassScope
from chorus.domain.compact import is_context_overflow
from chorus.domain.log import get_logger
from chorus.domain.memory import MemoryRecall
from chorus.domain.message import AssistantMessage, ToolCallSpec, ToolMessage, UserMessage
from chorus.domain.prompt.supervisor import SupervisorSystemInputs, SupervisorUserInputs
from chorus.domain.stream import consume_stream
from chorus.domain.trace import TracePhase, UserInput
from chorus.hooks import HookRegistry
from chorus.services.intent_state import IntentStateService
from chorus.services.memory import MemoryService
from chorus.services.compact import CompactService
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.services.trace import TraceService
from chorus.tools import ToolDispatch
from chorus.tools.framework import Suspend

_SUPERVISOR_MAX_STEPS = 20

_logger = get_logger("supervisor")


class SupervisorLoopStrategy(LoopStrategy):
    """supervisor 的回合自动机差异面：SSE 流式消费、成对落库、收尾钩子与意图状态注入。"""

    max_steps = _SUPERVISOR_MAX_STEPS

    def __init__(self, session_id, message_service, session_service, hooks,
                 intent_state: IntentStateService,
                 memory: MemoryRecall, compact: CompactService):
        self.session_id = session_id
        self._message = message_service
        self._session = session_service
        self._hooks = hooks
        self._intent_state = intent_state
        self._recall = memory
        self._compact = compact
        self._reactive_done = False
        self.retry_requested = False

    def message_start(self, ctx):
        return [MessageStartEvent(id=ctx.turn.message_id)]

    def provider_messages(self):
        system_inputs = SupervisorSystemInputs(digest=self._recall.digest)
        user_inputs = SupervisorUserInputs(
            memories=self._recall.items,
            intent_state=self._intent_state.get(self.session_id),
        )
        msgs = self._message.build_provider_messages(self.session_id, system_inputs.render_system_prompt())
        user_inputs.inject_user_context(msgs)
        return msgs

    def consume(self, stream):
        return consume_stream(stream)

    def after_tools(self, ctx, result, pairs):
        """成对落库，据是否命中挂起决定续跑或关流。"""
        msg = AssistantMessage.from_stream(
            self.session_id, result, message_id=ctx.turn.message_id,
            tool_calls=[ToolCallSpec.from_arguments(call.id, call.name, call.arguments) for call, _ in pairs]
        )
        self._message.append_assistant_message(msg)

        for call, dispatch in pairs:
            self._message.append_tool_message(
                self.session_id, tool_call_id=call.id, name=call.name,
                content=dispatch.outcome.content,
            )

        self._session.touch(self.session_id)
        events = self._intent_state.events_for_turn(
            self.session_id, ctx.turn.message_id, (call.name for call, _ in pairs),
        )
        events.extend(event for _, dispatch in pairs for event in dispatch.events)

        suspend = next((dispatch for _, dispatch in pairs if isinstance(dispatch.outcome, Suspend)), None)
        if suspend is not None:
            return self._handle_suspend(ctx, events)
        return LoopAction(LoopSignal.CONTINUE, events)

    def _handle_suspend(self, ctx, events):
        """挂起分支：关流但不视作完成，续写复用会话最新气泡。"""
        return LoopAction(LoopSignal.SUSPEND, self._finish_events(ctx, prefix=[*events, SuspendEvent()]))

    def after_text(self, ctx, result):
        """纯文本回复：落库并发完成事件与收尾钩子。"""
        msg = AssistantMessage.from_stream(self.session_id, result, message_id=ctx.turn.message_id)
        self._message.append_assistant_message(msg)
        self._session.touch(self.session_id)
        return LoopAction(LoopSignal.FINISH, self._finish_events(ctx))

    def _finish_events(self, ctx, prefix=()):
        """完成事件先行解禁前端，收尾钩子惰性随后执行，旁路调用不拖住关流。"""
        yield from prefix
        yield DoneEvent()
        yield from self._hooks.trigger("Stop", ctx)

    def on_truncation_exhausted(self, ctx):
        """放宽后仍截断：不落占位消息，直接收轮。"""
        return LoopAction(LoopSignal.FINISH, self._finish_events(ctx))

    def on_exhausted(self):
        return LoopAction(LoopSignal.FINISH, [ErrorEvent(content="主 Agent 未能完成本轮必要动作，请再试一次")])

    def on_error(self, ctx, error):
        # 输入超长先应急压缩并请求重跑一次，其余走占位消息关流
        if not self._reactive_done and is_context_overflow(error) and self._compact.reactive(ctx.session_id):
            self._reactive_done = True
            self.retry_requested = True
            _logger.warning("reactive compact done, retry loop", extra={"session_id": ctx.session_id})
            return LoopAction(LoopSignal.FINISH, [])
        try:
            self._message.append_error_placeholder(ctx.session_id, ctx.turn.message_id, error)
        except Exception:
            _logger.exception("failed to persist error placeholder", extra={"session_id": ctx.session_id})
        return LoopAction(LoopSignal.FINISH, [ErrorEvent(content=str(error))])


class SupervisorService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        hooks: HookRegistry,
        chat_model_provider: ChatModelProvider,
        task_service: TaskService,
        tool_dispatcher: ToolDispatch,
        loop: AgentLoop,
        intent_state: IntentStateService,
        memory_service: MemoryService,
        compact_service: CompactService,
        trace_service: TraceService,
    ):
        self._session = session_service
        self._message = message_service
        self._hooks = hooks
        self._models = chat_model_provider
        self._task = task_service
        self._tools = tool_dispatcher
        self._loop = loop
        self._intent_state = intent_state
        self._memory = memory_service
        self._compact = compact_service
        self._trace = trace_service

    def stream(
        self, session_id: str, user_message: str,
    ) -> Iterator[SseEvent]:
        """用户真实发话入口：先落用户消息，再跑 loop。"""
        reject = self._admit(session_id)
        if reject is not None:
            yield reject
            return

        message = self._message.append_user_message(session_id, user_message)
        self._session.touch(session_id)
        yield from self._emit_user_input(message)
        yield from self._run(session_id, user_message)

    def _emit_user_input(self, message: UserMessage) -> Iterator[SseEvent]:
        """落用户输入轨迹并发对应事件，复用消息时间戳保证排在召回之前。"""
        payload = UserInput(content=message.content)
        created_at = self._trace.add_trace(
            session_id=message.session_id,
            message_id=message.id,
            phase=TracePhase.USER_INPUT,
            payload=payload,
            created_at=message.created_at,
        )
        yield TraceEvent(
            phase=TracePhase.USER_INPUT,
            message_id=message.id,
            created_at=created_at,
            payload=payload.model_dump(),
        )


    def resume(self, session_id: str, tool_name: str, result_text: str) -> Iterator[SseEvent]:
        """解开挂起 loop 的通用原语：改写指定工具结果后续跑。"""
        reject = self._admit(session_id)
        if reject is not None:
            yield reject
            return

        self._message.rewrite_last_tool_result(session_id, tool_name, result_text)
        yield from self._run(session_id, None)

    def has_unreceipted_plan(self, session_id: str) -> bool:
        """收尾锁：末条消息是建图工具结果且无活跃任务，即确有未回执挂起。"""
        if self._task.count_active(session_id) > 0:
            return False
        messages = self._message.list_messages(session_id)
        last = messages[-1] if messages else None
        return isinstance(last, ToolMessage) and last.name == "create_plan"

    def _admit(self, session_id: str) -> Optional[SseEvent]:
        """入口业务门禁：有进行中任务则拒收。存在性由路由层 404 保证。"""
        if self._task.count_active(session_id) > 0:
            _logger.info("reject: active task in progress", extra={"session_id": session_id})
            return BusyEvent(content="该会话有创作任务进行中，请等待完成")
        return None

    def _run(self, session_id: str, user_message) -> Iterator[SseEvent]:
        """共用续跑内核：取模型、构造上下文与策略、跑 loop。"""
        entry = self._models.get_entry()
        schemas = self._tools.select_schemas(TOOL_WHITELISTS["supervisor"])
        memory = self._prepare_memory(session_id, user_message)
        ctx = AgentContext(
            session_id=session_id, user_message=user_message,
            tool_schemas=schemas, chat_model=entry.model_id,
            pricing=entry.pricing,
        )
        strategy = SupervisorLoopStrategy(
            session_id, self._message, self._session, self._hooks,
            intent_state=self._intent_state,
            memory=memory,
            compact=self._compact,
        )

        yield from self._run_with_retry(ctx, entry, strategy)

    def _run_with_retry(self, ctx, entry, strategy) -> Iterator[SseEvent]:
        """跑一遍 loop；因输入超长做过应急压缩则再跑一次，二次超长正常报错。"""
        yield from self._loop.run(ctx, entry=entry, strategy=strategy)
        if strategy.retry_requested:
            strategy.retry_requested = False
            yield from self._loop.run(ctx, entry=entry, strategy=strategy)

    def _prepare_memory(self, session_id: str, user_message) -> MemoryRecall:
        """入口同步召回一次，缓存进策略供每轮注入，工具循环内不重召。"""
        return self._memory.recall_for("supervisor", user_message or "", BypassScope(session_id=session_id))
