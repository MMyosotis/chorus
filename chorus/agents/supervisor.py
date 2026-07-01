# kitty/agents/supervisor.py
"""SupervisorService：supervisor SSE 流式 loop（沟通入口/出口 + 建图路由）。

主流程单文件可读全：append user → 每轮 build messages → 调模型 → consume_stream →
按 outcome 分流：无 tool_call → only_reply 文本；有 tool_call → 统一 dispatch →
Reply 回传继续 loop / Terminal 触发 handle_terminal done 收尾。loop 按
isinstance(outcome, ...) 分流，不认识工具名、不认 Terminal 载荷类型——工具副作用
在工具内收口，主流程只管终止。会话级创作准入：有活跃任务 yield BusyEvent 拒绝
（纵深防御，前端已挡但不可信）。横切（trace/title/异常收尾）挂扁平 hook。
"""
from __future__ import annotations

import json
import uuid
from typing import Iterator, Optional

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
        # 会话级创作准入：有活跃任务则拒绝（纵深防御，前端已挡但不可信）。
        # fail-closed 不回传模型——并发冲突模型纠正不了，user 消息不入库、模型不参与。
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
                ctx.turn.message_id = uuid.uuid4().hex
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
                    # only_reply：文本回复落库 + done
                    content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
                    self._message.append_assistant_message(
                        session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
                    )
                    self._session.touch(session_id)
                    yield DoneEvent()
                    yield from self._hooks.trigger("Stop", ctx)
                    return
                # 工具调用分支：统一 dispatch 所有 tool_call，按 outcome 分流
                got_terminal = yield from self._dispatch_tools(session_id, ctx, schemas)
                if got_terminal:
                    return  # Terminal 已结束本轮
        except Exception as e:
            ctx.outcome.exception = e
            yield from self._hooks.trigger("Error", ctx)
            yield ErrorEvent(content=str(e))

    def _dispatch_tools(
        self, session_id: str, ctx: AgentContext, schemas: list[dict],
    ) -> Iterator[SseEvent]:
        """一轮内 dispatch 所有 tool_call，收集后成对落库（一条 assistant + N tool），
        再按是否命中 Terminal 决定结束本轮或继续。

        generator：yield SSE 事件，return bool（是否命中 Terminal 结束本轮）。
        收集全部 (call, dispatch_result) 后落**一条** assistant(tool_calls=[全部]) + N 条
        tool(result)——OpenAI 多 tool_call 配对的真实结构，根除多 Reply tool_call 复用
        message_id 撞 messages PK 的回归。首个 Terminal 即结束本轮。
        """
        tool_ctx = ToolContext(session_id=session_id)
        pairs = []          # [(call, dispatch_result)] 按索引顺序
        terminal = None     # 首个 Terminal 的 (call, d)
        for _, tc in sorted(ctx.turn.accumulated_tool_calls.items()):
            call = ToolCall(id=tc.id, name=tc.name, arguments=_parse_args(tc.arguments))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments, "seq": tc.seq}
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
        # 一条 assistant(tool_calls=[全部]) + N tool(result) 成对落库——OpenAI 配对真实结构
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
        """assistant 内容：Terminal 轮用 friendly_reply（流程节拍气泡）；全 Reply 轮用模型文本。"""
        if terminal is not None:
            call, _ = terminal
            return call.arguments.get("friendly_reply") or "好的，开始为你创作"
        return "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None

    def _handle_terminal(self, session_id: str, ctx: AgentContext, call: ToolCall, d) -> Iterator[SseEvent]:
        """Terminal 分支：工具已在自身内完成副作用，主流程只做 done 收尾 + Stop hook。

        成对落库（assistant tool_calls + tool result）已在 _dispatch_tools 完成；
        Terminal 载荷由工具自洽，主流程不按载荷类型分流——只管终止本轮。
        """
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
