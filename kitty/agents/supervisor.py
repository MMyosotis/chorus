# kitty/agents/supervisor.py
"""SupervisorService：supervisor SSE 流式 loop（沟通入口/出口 + 建图路由）。

主流程单文件可读全：append user → 每轮 build messages → 调模型 → consume_stream →
按 outcome 分流：无 tool_call → only_reply 文本；有 tool_call → 统一 dispatch →
Reply 回传继续 loop / Terminal 触发 handle_terminal 建图+成对落库+done。loop 按
isinstance(outcome, ...) 分流，不认识工具名。会话级创作准入：有活跃任务 yield
BusyEvent 拒绝（纵深防御，前端已挡但不可信）。横切（trace/title/异常收尾）挂扁平 hook。
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional

from openai import OpenAI

from kitty.agents.runtime import AgentContext
from kitty.domain.events import (
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    SseEvent,
)
from kitty.domain.prompt import PromptContext, build_system_prompt
from kitty.domain.skill import SkillLoader, format_skill_hints
from kitty.domain.stream import consume_stream
from kitty.domain.task import ACTIVE_STATUSES
from kitty.hooks import HookRegistry
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.task import TaskRepository
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.tools import ToolCall, ToolRegistry, select_schemas_by_names
from kitty.tools.framework import Reply, Terminal, ToolCtxFactory

logger = logging.getLogger(__name__)

# supervisor 工具白名单（与 AGENT_PROFILES.tools 同构的单一真源）。
# 具体内容可后续调整；机制本身要求：supervisor 能力边界在此一处声明。
# supervisor 是传话筒/管人的领导，不碰产物——generate_image 等业务技能工具不对它开放。
SUPERVISOR_TOOLS = ("create_plan", "load_skill", "baidu_search")


@dataclass(frozen=True)
class ChatModelEntry:
    client: OpenAI
    model_id: str


class SupervisorService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        skill_loader: SkillLoader,
        hooks: HookRegistry,
        models: dict,
        default_model_id: str,
        max_tokens: int,
        task_repo: TaskRepository,
        conn: ConnectionFactory,
        tool_registry: ToolRegistry,
        tool_ctx_factory: ToolCtxFactory,
        clock=time.time,
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._models = models
        self._default_model_id = default_model_id
        self._max_tokens = max_tokens
        self._task_repo = task_repo
        self._conn = conn
        self._tools = tool_registry
        self._tool_ctx_factory = tool_ctx_factory
        self._clock = clock

    def stream(
        self, session_id: str, user_message: str, *,
        model: Optional[str] = None, image_model: Optional[str] = None,
        web_search: Optional[bool] = None,
    ) -> Iterator[SseEvent]:
        if not self._session.exists(session_id):
            yield ErrorEvent(content="session not found")
            return
        # 会话级创作准入：有活跃任务则拒绝（纵深防御，前端已挡但不可信）。
        # fail-closed 不回传模型——并发冲突模型纠正不了，user 消息不入库、模型不参与。
        if self._task_repo.count_by_session_statuses(session_id, ACTIVE_STATUSES) > 0:
            yield BusyEvent(content="该会话有创作任务进行中，请等待完成")
            return
        entry = self._models[model or self._default_model_id]
        schemas = self._tool_schemas(web_search)
        ctx = AgentContext(
            session_id=session_id, user_message=user_message,
            tool_schemas=schemas, image_model=image_model, chat_model=entry.model_id,
        )
        try:
            self._message.append_user_message(session_id, user_message)
            self._session.touch(session_id)
            i = 0
            while True:
                ctx.turn.reset(i)
                ctx.turn.message_id = uuid.uuid4().hex
                yield MessageStartEvent(id=ctx.turn.message_id)
                prompt = build_system_prompt(PromptContext(
                    skill_hints=format_skill_hints(self._skill.list_summaries()),
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
                i += 1
        except Exception as e:
            ctx.outcome.exception = e
            yield from self._hooks.trigger("Error", ctx)
            yield ErrorEvent(content=str(e))

    def _tool_schemas(self, web_search: Optional[bool]) -> list[dict]:
        """supervisor 工具白名单：从 registry 全集按 SUPERVISOR_TOOLS 筛，再按联网开关过滤。"""
        schemas = select_schemas_by_names(self._tools.schemas_openai(), SUPERVISOR_TOOLS)
        if web_search is False:
            schemas = [s for s in schemas
                       if s.get("function", {}).get("name") != "baidu_search"]
        return schemas

    def _dispatch_tools(
        self, session_id: str, ctx: AgentContext, schemas: list[dict],
    ) -> Iterator[SseEvent]:
        """逐个 dispatch tool_call，按 outcome 分流。

        generator：yield SSE 事件，return bool（是否命中 Terminal 结束本轮）。
        Reply 型回传继续 loop。OpenAI 单轮通常只一个 tool_call，但仍按多调用顺序处理；
        首个 Terminal 即结束。
        """
        tool_ctx = self._tool_ctx_factory(session_id, ctx.image_model)
        for _, tc in sorted(ctx.turn.accumulated_tool_calls.items()):
            call = ToolCall(id=tc["id"], name=tc["name"], arguments=_parse_args(tc["arguments"]))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._tools.format_display(call.name, call.arguments),
                self._tools.running_label(call.name),
            ))
            d = self._tools.dispatch(call, tool_ctx)
            list(self._hooks.trigger("PostToolUse", ctx, call_view, d.tool_result))
            if isinstance(d.outcome, Reply):
                # 成对落库：先 assistant(tool_calls) 再 tool(result)，满足 OpenAI 配对约束，
                # 下一轮 build_provider_messages 回放历史如实。content 取本轮模型文本（无则 None）。
                self._message.append_assistant_message(
                    session_id, message_id=ctx.turn.message_id,
                    content="".join(ctx.turn.text_parts) if ctx.turn.text_parts else None,
                    tool_calls=[_to_tool_call_spec(call)],
                )
                self._message.append_tool_message(
                    session_id, tool_call_id=call.id, name=call.name,
                    content=d.tool_result.content,
                )
                self._session.touch(session_id)
                continue
            if isinstance(d.outcome, Terminal):
                yield from self._handle_terminal(session_id, ctx, call, d)
                return True
        return False

    def _handle_terminal(self, session_id: str, ctx: AgentContext, call: ToolCall, d) -> Iterator[SseEvent]:
        """Terminal 分支：建图副作用 + 成对落库 + done（generator）。

        按载荷类型扩展（现阶段只 PlanRequest）。建图副作用（expand + 事务 insert）归此处。
        assistant(friendly_reply, tool_calls=[call]) + tool(result) 成对落库，满足 OpenAI
        配对约束，下一轮回放历史如实。建图成功只 yield done，建图状态靠前端轮询。
        """
        from kitty.domain.task import PlanRequest, expand_pipeline
        payload = d.outcome.payload
        if isinstance(payload, PlanRequest):
            tasks = expand_pipeline(payload.intent, payload.steps)
            now = self._clock()
            with self._conn.transaction():
                for t in tasks:
                    self._task_repo.insert(t.model_copy(update={
                        "session_id": session_id, "created_at": now, "updated_at": now,
                    }))
            friendly_reply = call.arguments.get("friendly_reply") or "好的，开始为你创作"
            self._message.append_assistant_message(
                session_id, message_id=ctx.turn.message_id, content=friendly_reply,
                tool_calls=[_to_tool_call_spec(call)],
            )
            self._message.append_tool_message(
                session_id, tool_call_id=call.id, name=call.name,
                content=d.tool_result.content,
            )
            self._session.touch(session_id)
            yield DoneEvent()
            yield from self._hooks.trigger("Stop", ctx)
            return
        # 未知 payload：回退 done（防御性，不应发生）
        yield DoneEvent()


def _to_tool_call_spec(call: ToolCall):
    from kitty.domain.message import ToolCallSpec
    return ToolCallSpec(id=call.id, name=call.name, arguments_json=json.dumps(call.arguments, ensure_ascii=False))


def _parse_args(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
