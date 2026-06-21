"""ChatService：agent loop 主流程。

stream() 线性展开主流程，单文件可读全（对齐 参考资料 s04「挂在循环上，
不写进循环里」）：核心业务提交（落库 / 构建 prompt / 执行工具 / SSE 核心事件 yield）
直接在 loop 内；扩展（trace / 标题 / 回滚）经 HookRegistry.trigger 挂在外面，fail-open。
核心步骤无 try/except → 异常上抛到外层 except → trigger("Error") + yield ErrorEvent（fail-closed）。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional

from openai import OpenAI

from kitty.domain.agent import AgentContext
from kitty.domain.events import (
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    SseEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from kitty.domain.message import ToolCallSpec
from kitty.domain.prompt import PromptContext, build_system_prompt
from kitty.domain.skill import SkillLoader, format_skill_hints
from kitty.domain.stream import consume_stream
from kitty.hooks import HookRegistry
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.tools import ToolCall, ToolCtxFactory, ToolRegistry, select_tool_schemas


@dataclass(frozen=True)
class ChatModelEntry:
    """运行时模型条目：OpenAI 兼容客户端 + 传给 API 的真实 model 名。"""

    client: OpenAI
    model_id: str


class ChatService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        skill_loader: SkillLoader,
        hooks: HookRegistry,
        tool_registry: ToolRegistry,
        tool_ctx_factory: ToolCtxFactory,
        models: dict[str, ChatModelEntry],
        default_model_id: str,
        max_tokens: int,
        tool_schemas: list[dict],
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._tool_registry = tool_registry
        self._tool_ctx_factory = tool_ctx_factory
        self._models = models
        self._default_model_id = default_model_id
        self._max_tokens = max_tokens
        self._tool_schemas = tool_schemas

    def stream(
        self,
        session_id: str,
        user_message: str,
        *,
        model: Optional[str] = None,
        image_model: Optional[str] = None,
        web_search: Optional[bool] = None,
    ) -> Iterator[SseEvent]:
        if not self._session.exists(session_id):
            yield ErrorEvent(content="session not found")
            return

        # None 视为默认开，领域函数只接确定 bool
        schemas = _select_schemas(self._tool_schemas, web_search=web_search is not False)
        entry = self._models[model or self._default_model_id]
        ctx = AgentContext(
            session_id=session_id,
            user_message=user_message,
            tool_schemas=schemas,
            image_model=image_model,
            chat_model=entry.model_id,
        )

        try:
            # 核心：本轮 user 消息落库（fail-closed）
            self._message.append_user_message(session_id, user_message)
            self._session.touch(session_id)

            i = 0
            while True:
                ctx.turn.reset(i)
                ctx.turn.message_id = uuid.uuid4().hex
                yield MessageStartEvent(id=ctx.turn.message_id)

                # 核心：构建 provider_messages（fail-closed）
                prompt = build_system_prompt(PromptContext(
                    skill_hints=format_skill_hints(self._skill.list_summaries()),
                ))
                ctx.turn.provider_messages = self._message.build_provider_messages(session_id, prompt)

                # 扩展：trace 写 model_request（fail-open）
                yield from self._hooks.trigger("BeforeModelRequest", ctx)

                stream = entry.client.chat.completions.create(
                    model=entry.model_id,
                    messages=ctx.turn.provider_messages,
                    tools=ctx.tool_schemas,
                    max_tokens=self._max_tokens,
                    stream=True,
                )
                # 领域：消费流式，yield reasoning/token，return StreamResult
                result = yield from consume_stream(stream)
                ctx.turn.apply_stream(result)

                # 扩展：trace 写 model_response（fail-open，文本/工具两类分支共用）
                yield from self._hooks.trigger("AfterModelResponse", ctx)

                is_text = (
                    ctx.turn.finish_reason != "tool_calls"
                    or not ctx.turn.accumulated_tool_calls
                )
                if is_text:
                    # 核心：落 assistant 文本消息（fail-closed）
                    content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
                    self._message.append_assistant_message(
                        session_id, message_id=ctx.turn.message_id,
                        content=content, tool_calls=[],
                    )
                    self._session.touch(session_id)
                    # done 先于标题：前端收到 done 即解禁输入框；标题生成是非流式 OpenAI
                    # 调用（慢），若先发会阻塞 done、让输入框一直禁用。路由在 done 后释放会话锁，
                    # 故 title_update 在不持锁状态下产出（与原 hook 顺序一致）。
                    yield DoneEvent()
                    yield from self._hooks.trigger("Stop", ctx)
                    return

                # 核心：落 assistant(tool_calls) + 执行工具 + 落 tool 消息 + yield 事件（fail-closed）
                yield from self._execute_tools(ctx)
                i += 1
        except Exception as e:
            ctx.outcome.exception = e
            # 扩展：append [Error] 关闭本轮（fail-open，best-effort）
            yield from self._hooks.trigger("Error", ctx)
            yield ErrorEvent(content=str(e))

    def _execute_tools(self, ctx: AgentContext) -> Iterator[SseEvent]:
        """核心：落 assistant(tool_calls) → 逐个执行工具 → 落 tool 消息 → yield 事件。"""
        tool_calls_list = _materialize(ctx)
        specs = [
            ToolCallSpec(id=tc["id"], name=tc["function"]["name"], arguments_json=tc["function"]["arguments"])
            for tc in tool_calls_list
        ]
        content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
        self._message.append_assistant_message(
            ctx.session_id, message_id=ctx.turn.message_id,
            content=content, tool_calls=specs,
        )
        self._session.touch(ctx.session_id)

        tool_ctx = self._tool_ctx_factory(ctx.session_id, ctx.image_model)
        for tc in tool_calls_list:
            call = ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=_parse_args(tc["function"]["arguments"]),
            )
            display = self._tool_registry.format_display(call.name, call.arguments)
            running_label = self._tool_registry.running_label(call.name)
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}

            # 扩展：trace 写 tool_call（fail-open）
            yield from self._hooks.trigger("PreToolUse", ctx, call_view, display, running_label)
            yield ToolCallEvent(
                id=call.id, name=call.name, arguments=call.arguments,
                display=display, running_label=running_label,
            )

            # 核心：执行工具（dispatch 已包错返回 ToolResult，不抛）
            result = self._tool_registry.dispatch(call, tool_ctx)
            self._message.append_tool_message(
                ctx.session_id, tool_call_id=call.id, name=call.name, content=result.content,
            )
            self._session.touch(ctx.session_id)

            # 扩展：trace 写 tool_result（fail-open）
            yield from self._hooks.trigger("PostToolUse", ctx, call_view, result)
            yield ToolResultEvent(
                tool_call_id=call.id, name=call.name,
                content=result.content, duration_ms=result.duration_ms,
            )


def _select_schemas(schemas: list[dict], *, web_search: bool) -> list[dict]:
    """按联网搜索开关过滤工具 schema：关闭时移除 baidu_search。"""
    return select_tool_schemas(schemas, web_search=web_search)


def _materialize(ctx: AgentContext) -> list[dict]:
    accumulated = ctx.turn.accumulated_tool_calls or {}
    return [
        {
            "id": e["id"],
            "type": "function",
            "function": {"name": e["name"], "arguments": e["arguments"]},
        }
        for _, e in sorted(accumulated.items())
    ]


def _parse_args(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
