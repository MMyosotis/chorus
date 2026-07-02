"""主调度 agent：流式对话入口，普通对话直接回复，创作请求经建图工具路由。

主流程：追加用户消息 → 每轮拼消息调模型 → 按是否有工具调用分流——无则文本回复收尾，
有则统一派发工具，据返回是回复还是终止决定继续或结束。主流程不识工具名与终止载荷，
工具副作用在工具内收口。有活跃创作任务时拒绝新请求。横切经扁平钩子。
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

import uuid6

from chorus.agents.runtime import AgentContext
from chorus.domain.events import (
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
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
from chorus.tools import ToolCall, ToolContext, ToolDispatch
from chorus.tools.framework import Reply, Terminal


class SupervisorService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        skill_loader: SkillLoader,
        hooks: HookRegistry,
        chat_model_provider: ChatModelProvider,
        max_tokens: int,
        task_repo: TaskRepository,
        tool_dispatcher: ToolDispatch,
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._models = chat_model_provider
        self._max_tokens = max_tokens
        self._task_repo = task_repo
        self._tools = tool_dispatcher

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
        try:
            self._message.append_user_message(session_id, user_message)
            self._session.touch(session_id)
            while True:
                ctx.turn.reset()
                ctx.turn.message_id = str(uuid6.uuid7())
                yield MessageStartEvent(id=ctx.turn.message_id)
                prompt = build_system_prompt(PromptContext(
                    skill_hints=self._skill.format_hints(),
                ))
                ctx.turn.provider_messages = self._message.build_provider_messages(session_id, prompt)
                yield from self._hooks.trigger("BeforeModelRequest", ctx)
                stream = entry.client.chat.completions.create(
                    model=entry.model_id, messages=ctx.turn.provider_messages,
                    tools=schemas, max_tokens=self._max_tokens, stream=True,
                )
                result = yield from consume_stream(stream)
                ctx.turn.apply_stream(result)
                yield from self._hooks.trigger("AfterModelResponse", ctx)

                if not ctx.turn.accumulated_tool_calls:
                    # 纯文本回复：落库并收尾
                    content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
                    self._message.append_assistant_message(
                        session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
                    )
                    self._session.touch(session_id)
                    yield DoneEvent()
                    yield from self._hooks.trigger("Stop", ctx)
                    return
                # 工具调用分支：统一派发，据是否命中终止决定结束或继续
                got_terminal = yield from self._dispatch_tools(session_id, ctx, schemas)
                if got_terminal:
                    return  # 终止已结束本轮
        except Exception as e:
            ctx.outcome.exception = e
            yield from self._hooks.trigger("Error", ctx)
            yield ErrorEvent(content=str(e))

    def _dispatch_tools(
        self, session_id: str, ctx: AgentContext, schemas: list[dict],
    ) -> Iterator[SseEvent]:
        """一轮内派发所有工具调用，成对落库（一条助手消息带全部调用 + N 条工具结果），
        再据是否命中终止决定结束本轮或继续。
        """
        tool_ctx = ToolContext(session_id=session_id)
        pairs = []          # 调用与结果按索引顺序
        terminal = None     # 首个终止结果
        for _, tc in sorted(ctx.turn.accumulated_tool_calls.items()):
            call = ToolCall(id=tc.id, name=tc.name, arguments=_parse_args(tc.arguments))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._tools.format_display(call.name, call.arguments),
                self._tools.running_label(call.name),
            ))
            d = self._tools.dispatch(call, tool_ctx)
            list(self._hooks.trigger("PostToolUse", ctx, call_view, d))
            pairs.append((call, d))
            if isinstance(d.outcome, Terminal) and terminal is None:
                terminal = (call, d)
        # 一条助手消息带全部调用 + N 条工具结果，成对落库
        self._message.append_assistant_message(
            session_id, message_id=ctx.turn.message_id,
            content=self._turn_content(ctx, terminal),
            tool_calls=[_to_tool_call_spec(c) for c, _ in pairs],
        )
        for call, d in pairs:
            self._message.append_tool_message(
                session_id, tool_call_id=call.id, name=call.name,
                content=d.outcome.content,
            )
        self._session.touch(session_id)
        if terminal is not None:
            yield from self._handle_terminal(session_id, ctx, terminal[0], terminal[1])
            return True
        return False

    def _turn_content(self, ctx: AgentContext, terminal) -> Optional[str]:
        """助手内容：终止轮用工具带的友好回复，纯回复轮用模型文本。"""
        if terminal is not None:
            call, _ = terminal
            return call.arguments.get("friendly_reply") or "好的，开始为你创作"
        return "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None

    def _handle_terminal(self, session_id: str, ctx: AgentContext, call: ToolCall, d) -> Iterator[SseEvent]:
        """终止分支：工具副作用已在工具内完成，主流程只做收尾。"""
        self._session.touch(session_id)
        yield DoneEvent()
        yield from self._hooks.trigger("Stop", ctx)


def _to_tool_call_spec(call: ToolCall):
    from chorus.domain.message import ToolCallSpec
    return ToolCallSpec(id=call.id, name=call.name, arguments_json=json.dumps(call.arguments, ensure_ascii=False))


def _parse_args(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
