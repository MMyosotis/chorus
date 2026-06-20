"""ChatService：agent loop 主流程（plan 检验3 的生命周期图对应此处的 stream）。

单一叙事：stream() 线性展开 loop，每个 hook 调用点用注释标注对数据 / ctx 的副作用，
与 plan 9.3 节生命周期图一一对应。所有横切逻辑（trace / 持久化 / 标题 / 回滚 / 工具）
都在 hook 里，本类只做循环控制 + LLM 调用 + 流累积。
"""

from __future__ import annotations

from time import perf_counter
from typing import Iterable, Iterator, Optional

from openai import OpenAI

from kitty.domain.agent import AgentContext
from kitty.domain.events import (
    ErrorEvent,
    ReasoningDoneEvent,
    ReasoningEvent,
    SseEvent,
    TokenEvent,
)
from kitty.domain.trace import ThinkingSegment
from kitty.hooks.manager import HookManager
from kitty.services.session import SessionService


class ChatService:
    def __init__(
        self,
        session_service: SessionService,
        hook_manager: HookManager,
        openai_client: OpenAI,
        model_id: str,
        max_tokens: int,
        max_iterations: int,
        tool_schemas: list[dict],
    ):
        self._session = session_service
        self._hooks = hook_manager
        self._client = openai_client
        self._model = model_id
        self._max_tokens = max_tokens
        self._max_iterations = max_iterations
        self._tool_schemas = tool_schemas

    def stream(self, session_id: str, user_message: str) -> Iterator[SseEvent]:
        if not self._session.exists(session_id):
            yield ErrorEvent(content="session not found")
            return

        # 入口前 messages 数量 = 回滚锚点（SystemPromptHook append user 之前的快照）
        snapshot_len = len(self._session.list_messages(session_id))
        ctx = AgentContext(
            session_id=session_id,
            user_message=user_message,
            history_snapshot_len=snapshot_len,
            tool_schemas=self._tool_schemas,
        )

        # LoopStart: SystemPromptHook 把本轮 user 消息 append 入库（messages 表 +1）
        yield from self._hooks.on_loop_start(ctx)

        try:
            for i in range(self._max_iterations):
                ctx.turn.reset(i)
                # IterationStart: 分配 message_id（本轮 assistant），yield message_start
                yield from self._hooks.on_iteration_start(ctx)
                # BeforeModelRequest: Sanitizer 调 build_provider_messages 写 ctx.turn.provider_messages；
                #                      Trace 写 model_request trace 行
                yield from self._hooks.on_before_model_request(ctx)

                stream = self._client.chat.completions.create(
                    model=self._model,
                    messages=ctx.turn.provider_messages,
                    tools=ctx.tool_schemas,
                    max_tokens=self._max_tokens,
                    stream=True,
                )
                # 消费流：yield reasoning/token 事件，累积 text_parts / tool_calls / thinking
                (ctx.turn.text_parts, ctx.turn.accumulated_tool_calls,
                 ctx.turn.finish_reason, ctx.turn.thinking_segments) = yield from consume_stream(stream)

                if ctx.turn.finish_reason != "tool_calls" or not ctx.turn.accumulated_tool_calls:
                    # AssistantTextResponse: Trace 写 model_response；TextResponse append assistant
                    #                         文本消息 + yield done；Title 首轮生成标题
                    yield from self._hooks.on_assistant_text_response(ctx)
                    return

                # ToolCallsDetected: Trace 写 model_response；ToolCall append assistant(tool_calls)、
                #                    逐个执行工具、append tool 消息、yield tool_call/tool_result
                yield from self._hooks.on_tool_calls_detected(ctx)

            ctx.outcome.done_reason = "max_iterations_reached"
            # LoopEnd: Trace 写 loop_end；Persistence yield done(reason)
            yield from self._hooks.on_loop_end(ctx)
        except Exception as e:
            ctx.outcome.exception = e
            # LoopError: Rollback 删除本轮新增 messages + traces，yield error
            yield from self._hooks.on_loop_error(ctx)


# ------------------------------------------------------------------
# 流式响应累积：consume_stream 消费 OpenAI 流，yield 思考/正文事件并累积工具调用；
# 返回 (text_parts, tool_calls, finish_reason, thinking_segments)。
def consume_stream(stream) -> Iterator[SseEvent]:
    accumulated: dict[int, dict] = {}
    text_parts: list[str] = []
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = []

    cur_parts: list[str] = []
    started_at: Optional[float] = None
    in_progress = False

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta
        if choice.finish_reason is not None:
            finish_reason = choice.finish_reason

        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            if not in_progress:
                started_at = perf_counter()
                in_progress = True
            cur_parts.append(reasoning)
            yield ReasoningEvent(content=reasoning)

        if in_progress and (delta.content or delta.tool_calls):
            duration = _close_thinking(cur_parts, started_at, thinking_segments)
            yield ReasoningDoneEvent(duration_ms=duration)

        if delta.content:
            text_parts.append(delta.content)
            yield TokenEvent(content=delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                _merge_tool_call(accumulated, tc)

    if in_progress:
        duration = _close_thinking(cur_parts, started_at, thinking_segments)
        yield ReasoningDoneEvent(duration_ms=duration)

    return text_parts, accumulated, finish_reason, thinking_segments


def _close_thinking(parts: list[str], started_at: Optional[float], segments: list[ThinkingSegment]) -> int:
    if started_at is None:
        duration = 0
    else:
        duration = int((perf_counter() - started_at) * 1000)
    segments.append(ThinkingSegment(text="".join(parts), duration_ms=duration))
    parts.clear()
    return duration


def _merge_tool_call(accumulated: dict[int, dict], tc_delta) -> None:
    idx = tc_delta.index
    entry = accumulated.setdefault(idx, {"id": "", "name": "", "arguments": ""})
    if tc_delta.id:
        entry["id"] = tc_delta.id
    if tc_delta.function:
        if tc_delta.function.name:
            entry["name"] = tc_delta.function.name
        if tc_delta.function.arguments:
            entry["arguments"] += tc_delta.function.arguments
