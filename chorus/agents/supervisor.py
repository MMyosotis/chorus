"""主调度 agent：流式对话入口，普通对话直接回复，创作请求经建图工具路由。

业务差异进策略，主流程不识工具名与终止载荷，有活跃创作任务时拒绝新请求。
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
    IntentStateEvent,
    SseEvent,
)
from chorus.domain.intent import empty_intent_state
from chorus.domain.prompt import PromptContext, build_system_prompt
from chorus.domain.skill import SkillLoader
from chorus.domain.stream import consume_stream
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import ACTIVE_STATUSES
from chorus.hooks import HookRegistry
from chorus.repo.task import TaskRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.services.intent_state import IntentStateService
from chorus.services.session import SessionService
from chorus.tools import ToolCall, ToolDispatch
from chorus.tools.framework import Terminal


_INTENT_EVENT_TOOLS = {"update_intent_state", "create_plan"}

_FORCE_AFTER_TEXT = (
    "用户已经确认意图，当前回合必须调用 create_plan。"
    "不要继续澄清，除非 create_plan 工具返回参数纠错。"
)
_FORCE_AFTER_TOOLS = (
    "用户已经确认意图，但你上一轮没有调用 create_plan。"
    "请立刻基于 current_intent_state 和历史对话调用 create_plan。"
)


class SupervisorLoopStrategy:
    """supervisor 的回合自动机差异面：SSE 流式消费、成对落库、收尾钩子与意图状态注入。"""

    max_steps = None

    def __init__(self, session_id, message_service, session_service, hooks,
                 skill_loader, schemas, intent_state=None, enforce_terminal=False):
        self.session_id = session_id
        self._message = message_service
        self._session = session_service
        self._hooks = hooks
        self._skill = skill_loader
        self.schemas = schemas
        self._intent_state = intent_state or _NullIntentStateService()
        self._enforce_terminal = enforce_terminal
        self._force_instruction = ""
        self._pending_intent_events: list = []
        self.max_steps = 6 if enforce_terminal else None

    def before_turn(self):
        self._pending_intent_events = []
        return True

    def provider_messages(self):
        prompt = build_system_prompt(PromptContext(
            skill_hints=self._skill.format_hints(),
            intent_state=self._intent_state.get(self.session_id),
        ))
        if self._force_instruction:
            prompt = f"{prompt}\n\n## 本轮系统提醒\n{self._force_instruction}"
        return self._message.build_provider_messages(self.session_id, prompt)

    def consume(self, stream):
        return consume_stream(stream)

    def before_dispatch(self, call):
        pass

    def after_dispatch(self, call, d):
        if call.name in _INTENT_EVENT_TOOLS:
            self._pending_intent_events.append(
                IntentStateEvent(state=self._intent_state.get(self.session_id).public_dict())
            )

    def after_tools(self, ctx, result, pairs):
        """成对落库，据是否命中终止决定继续或结束。"""
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
        events = list(self._pending_intent_events)
        self._pending_intent_events = []

        if terminal is not None:
            return LoopAction(LoopSignal.FINISH, events + list(self._handle_terminal(ctx)))
        if self._enforce_terminal:
            self._force_instruction = _FORCE_AFTER_TOOLS
            return LoopAction(LoopSignal.CONTINUE, events)
        return LoopAction(LoopSignal.CONTINUE, events)

    def after_text(self, ctx, result):
        """纯文本回复：落库并发完成事件与收尾钩子。强制建图路径下不落库直接续轮。"""
        if self._enforce_terminal:
            self._force_instruction = _FORCE_AFTER_TEXT
            return LoopAction(LoopSignal.CONTINUE, [])

        content = "".join(result.text_parts) if result.text_parts else None
        self._message.append_assistant_message(
            self.session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
        )
        self._session.touch(self.session_id)

        events = [DoneEvent()] + list(self._hooks.trigger("Stop", ctx))
        return LoopAction(LoopSignal.FINISH, events)

    def on_exhausted(self):
        return LoopAction(LoopSignal.FINISH, [ErrorEvent(content="主 Agent 未能完成本轮必要动作，请再试一次")])

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
        intent_state: IntentStateService | None = None,
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._models = chat_model_provider
        self._task_repo = task_repo
        self._tools = tool_dispatcher
        self._loop = loop
        self._intent_state = intent_state or _NullIntentStateService()

    def stream(
        self, session_id: str, user_message: str, *, require_create_plan: bool = False,
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
            intent_state=self._intent_state, enforce_terminal=require_create_plan,
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


class _NullIntentStateService:
    def get(self, session_id: str):
        return empty_intent_state(session_id)
