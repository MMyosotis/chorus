"""主调度 agent：流式对话入口，普通对话直接回复，创作请求经建图工具路由。

主流程退化为「入口准入 + 构造 strategy + 跑 kernel」：追加用户消息 → AgentLoop.run 驱动
最小回合自动机，supervisor 的业务差异（SSE 流式消费 + 成对落库 + Stop 收尾）全部进
SupervisorLoopStrategy。主流程不识工具名与终止载荷，工具副作用在工具内收口。有活跃创作
任务时拒绝新请求。横切经扁平钩子。
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

from chorus.agents.loop import AgentLoop, LoopAction, LoopSignal
from chorus.agents.runtime import AgentContext
from chorus.domain.events import (
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    SseEvent,
)
from chorus.domain.prompt import PromptContext, build_system_prompt
from chorus.domain.skill import SkillLoader
from chorus.domain.stream import consume_stream
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import ACTIVE_STATUSES
from chorus.hooks import HookRegistry
from chorus.repo.task import TaskRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.tools import ToolCall, ToolDispatch
from chorus.tools.framework import Terminal


class SupervisorLoopStrategy:
    """supervisor 的回合自动机差异面：SSE 流式消费 + 成对落库 + Stop 收尾。"""

    max_steps = None

    def __init__(self, session_id, message_service, session_service, hooks,
                 skill_loader, schemas):
        self.session_id = session_id
        self._message = message_service
        self._session = session_service
        self._hooks = hooks
        self._skill = skill_loader
        self.schemas = schemas

    def before_turn(self, ctx, step):
        return True

    def provider_messages(self, ctx):
        prompt = build_system_prompt(PromptContext(skill_hints=self._skill.format_hints()))
        return self._message.build_provider_messages(self.session_id, prompt)

    def tool_schemas(self, ctx):
        return self.schemas

    def consume(self, stream):
        return consume_stream(stream)

    def before_dispatch(self, call):
        pass

    def after_dispatch(self, call, d):
        pass

    def after_tools(self, ctx, result, pairs):
        """成对落库（一条 assistant 带全部 tool_calls + N tool），据是否命中终止决定继续/结束。"""
        terminal = next(((c, d) for c, d in pairs if isinstance(d.outcome, Terminal)), None)
        content = self._turn_content(ctx, terminal)
        self._message.append_assistant_message(
            self.session_id, message_id=ctx.turn.message_id,
            content=content,
            tool_calls=[_to_tool_call_spec(c) for c, _ in pairs],
        )
        for call, d in pairs:
            self._message.append_tool_message(
                self.session_id, tool_call_id=call.id, name=call.name,
                content=d.outcome.content,
            )
        self._session.touch(self.session_id)
        if terminal is None:
            return LoopAction(LoopSignal.CONTINUE, [])
        return LoopAction(LoopSignal.FINISH, list(self._handle_terminal(ctx)))

    def after_text(self, ctx, result):
        """纯文本回复：落库 + done + Stop 收尾。"""
        content = "".join(result.text_parts) if result.text_parts else None
        self._message.append_assistant_message(
            self.session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
        )
        self._session.touch(self.session_id)
        events = [DoneEvent()] + list(self._hooks.trigger("Stop", ctx))
        return LoopAction(LoopSignal.FINISH, events)

    def on_exhausted(self, ctx):
        return LoopAction(LoopSignal.FINISH, [])  # max_steps=None 不可达

    def on_error(self, ctx, error):
        events = list(self._hooks.trigger("Error", ctx)) + [ErrorEvent(content=str(error))]
        return LoopAction(LoopSignal.FINISH, events)

    def _turn_content(self, ctx, terminal):
        """助手内容：终止轮用工具带的友好回复，纯回复轮用模型文本。"""
        if terminal is not None:
            call, _ = terminal
            return call.arguments.get("friendly_reply") or "好的，开始为你创作"
        return "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None

    def _handle_terminal(self, ctx):
        """终止分支：工具副作用已在工具内完成，主流程只做收尾。"""
        self._session.touch(self.session_id)
        yield DoneEvent()
        yield from self._hooks.trigger("Stop", ctx)


class SupervisorService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        skill_loader: SkillLoader,
        hooks: HookRegistry,
        chat_model_provider: ChatModelProvider,
        task_repo: TaskRepository,
        tool_dispatcher: ToolDispatch,
        loop: AgentLoop,
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._models = chat_model_provider
        self._task_repo = task_repo
        self._tools = tool_dispatcher
        self._loop = loop

    def stream(
        self, session_id: str, user_message: str,
    ) -> Iterator[SseEvent]:
        if not self._session.exists(session_id):
            yield ErrorEvent(content="session not found")
            return
        # 会话级创作准入：有活跃任务则拒绝，不回传模型
        if self._task_repo.count_by_session_statuses(session_id, ACTIVE_STATUSES) > 0:
            yield BusyEvent(content="该会话有创作任务进行中，请等待完成")
            return
        entry = self._models.get_entry()
        schemas = self._tools.select_schemas(TOOL_WHITELISTS["supervisor"])
        ctx = AgentContext(
            session_id=session_id, user_message=user_message,
            tool_schemas=schemas, chat_model=entry.model_id,
        )
        strategy = SupervisorLoopStrategy(
            session_id, self._message, self._session, self._hooks, self._skill, schemas,
        )
        try:
            self._message.append_user_message(session_id, user_message)
            self._session.touch(session_id)
            yield from self._loop.run(ctx, entry=entry, strategy=strategy)
        except Exception as e:
            ctx.outcome.exception = e
            yield from strategy.on_error(ctx, e).events


def _to_tool_call_spec(call: ToolCall):
    from chorus.domain.message import ToolCallSpec
    return ToolCallSpec(id=call.id, name=call.name, arguments_json=json.dumps(call.arguments, ensure_ascii=False))
