"""主调度 agent：流式对话入口，普通对话直接回复，创作请求经建图工具路由。

业务差异进策略，主流程不识工具名与挂起载荷，有活跃创作任务时拒绝新请求。
意图记录与建图均靠 prompt 引导 + 工具内校验，不做代码层强制拦截。
"""
from __future__ import annotations

from typing import Iterator, Optional

from chorus.agents.chat_model import ChatModelProvider
from chorus.agents.loop import AgentLoop, LoopAction, LoopSignal, LoopStrategy
from chorus.agents.runtime import AgentContext
from chorus.config import TOOL_WHITELISTS
from chorus.domain.events import (
    ArchivedEvent,
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    SseEvent,
    SuspendEvent,
)
from chorus.domain.log import get_logger
from chorus.domain.memory import MemoryRecall
from chorus.domain.message import ToolCallSpec
from chorus.domain.prompt import SYSTEM_PROMPT, PromptContext, UserMessageContext, build_system_prompt, inject_user_blocks
from chorus.domain.skill import SkillLoader
from chorus.domain.stream import consume_stream
from chorus.hooks import HookRegistry
from chorus.services.intent_state import IntentStateService
from chorus.services.memory import MemoryService
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.tools import ToolDispatch
from chorus.tools.framework import Suspend

_SUPERVISOR_MAX_STEPS = 20

_logger = get_logger("supervisor")


class SupervisorLoopStrategy(LoopStrategy):
    """supervisor 的回合自动机差异面：SSE 流式消费、成对落库、收尾钩子与意图状态注入。"""

    max_steps = _SUPERVISOR_MAX_STEPS

    def __init__(self, session_id, message_service, session_service, hooks,
                 intent_state: IntentStateService, skill_loader, tool_names: tuple,
                 memory: MemoryRecall):
        self.session_id = session_id
        self._message = message_service
        self._session = session_service
        self._hooks = hooks
        self._intent_state = intent_state
        self._skill_loader = skill_loader
        self._tool_names = tool_names
        self._recall = memory

    def message_start(self, ctx):
        return [MessageStartEvent(id=ctx.turn.message_id)]

    def provider_messages(self):
        prompt = build_system_prompt(PromptContext(
            base=SYSTEM_PROMPT,
            tool_names=self._tool_names,
            skill_loader=self._skill_loader,
            memory_digest=self._recall.digest,
        ))
        msgs = self._message.build_provider_messages(self.session_id, prompt)
        inject_user_blocks(msgs, UserMessageContext(
            intent_state=self._intent_state.get(self.session_id),
            recalled_memories=self._recall.items,
        ))
        return msgs

    def consume(self, stream):
        return consume_stream(stream)

    def after_tools(self, ctx, result, pairs):
        """成对落库，据是否命中挂起决定续跑或关流。"""
        suspend = next(((call, dispatch) for call, dispatch in pairs if isinstance(dispatch.outcome, Suspend)), None)
        content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None

        self._message.append_assistant_message(
            self.session_id, message_id=ctx.turn.message_id,
            content=content,
            tool_calls=[ToolCallSpec.from_arguments(call.id, call.name, call.arguments) for call, _ in pairs],
        )
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

        if suspend is not None:
            return self._handle_suspend(ctx, events)
        return LoopAction(LoopSignal.CONTINUE, events)

    def _handle_suspend(self, ctx, events):
        """挂起分支：关流但不视作完成，续写复用会话最新气泡。"""
        self._session.touch(self.session_id)
        return LoopAction(LoopSignal.SUSPEND, events + [
            SuspendEvent(),
            DoneEvent(),
            *self._hooks.trigger("Stop", ctx),
        ])

    def after_text(self, ctx, result):
        """纯文本回复：落库并发完成事件与收尾钩子。"""
        if result.finish_reason == "length" and not result.text_parts:
            content = "这轮想得太久没回出来，再发一次试试，或者把要求说细一点。"
        else:
            content = "".join(result.text_parts) if result.text_parts else None
        self._message.append_assistant_message(
            self.session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
        )
        self._session.touch(self.session_id)

        # 完成事件先出解禁前端，收尾钩子急切执行
        stop_events = list(self._hooks.trigger("Stop", ctx))
        return LoopAction(LoopSignal.FINISH, [DoneEvent(), *stop_events])

    def on_exhausted(self):
        return LoopAction(LoopSignal.FINISH, [ErrorEvent(content="主 Agent 未能完成本轮必要动作，请再试一次")])

    def on_error(self, ctx, error):
        try:
            self._message.append_assistant_message(
                ctx.session_id, message_id=ctx.turn.message_id,
                content=f"[Error] {error}", tool_calls=[],
            )
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
        skill_loader: SkillLoader,
        memory_service: MemoryService,
    ):
        self._session = session_service
        self._message = message_service
        self._hooks = hooks
        self._models = chat_model_provider
        self._task = task_service
        self._tools = tool_dispatcher
        self._loop = loop
        self._intent_state = intent_state
        self._skill = skill_loader
        self._memory = memory_service

    def stream(
        self, session_id: str, user_message: str,
    ) -> Iterator[SseEvent]:
        """用户真实发话入口：先落用户消息，再跑 loop。"""
        reject = self._admit(session_id)
        if reject is not None:
            yield reject
            return

        self._message.append_user_message(session_id, user_message)
        self._session.touch(session_id)
        yield from self._run(session_id, user_message)

    def resume(self, session_id: str, tool_name: str, result_text: str) -> Iterator[SseEvent]:
        """解开挂起 loop 的通用原语：改写指定工具结果后续跑。"""
        reject = self._admit(session_id)
        if reject is not None:
            yield reject
            return

        self._message.rewrite_last_tool_result(session_id, tool_name, result_text)
        yield from self._run(session_id, None)

    def _admit(self, session_id: str) -> Optional[SseEvent]:
        """入口业务门禁：会话已定稿或有进行中任务则拒收。存在性由路由层 404 保证。"""
        if self._task.is_finalized(session_id):
            _logger.info("reject: session finalized", extra={"session_id": session_id})
            return ArchivedEvent(content="本篇已定稿存档，请新建会话开始下一篇")
        if self._task.count_active(session_id) > 0:
            _logger.info("reject: active task in progress", extra={"session_id": session_id})
            return BusyEvent(content="该会话有创作任务进行中，请等待完成")
        return None

    def _run(self, session_id: str, user_message) -> Iterator[SseEvent]:
        """共用续跑内核：取模型、构造上下文与策略、跑 loop。"""
        entry = self._models.get_entry()
        schemas = self._tools.select_schemas(TOOL_WHITELISTS["supervisor"])
        memory = self._prepare_memory(user_message)
        ctx = AgentContext(
            session_id=session_id, user_message=user_message,
            tool_schemas=schemas, chat_model=entry.model_id,
        )
        strategy = SupervisorLoopStrategy(
            session_id, self._message, self._session, self._hooks,
            intent_state=self._intent_state,
            skill_loader=self._skill,
            tool_names=TOOL_WHITELISTS["supervisor"],
            memory=memory,
        )

        yield from self._loop.run(ctx, entry=entry, strategy=strategy)

    def _prepare_memory(self, user_message) -> MemoryRecall:
        """入口同步召回一次，缓存进策略供每轮注入，工具循环内不重召。"""
        return self._memory.recall_for("supervisor", user_message or "")
