"""流式响应消费：把 OpenAI 流式 chunk 的增量翻译成领域状态 + SSE 事件。

纯函数式变换（零 IO、零副作用），与 domain/message.build_provider_messages 同层——
把"流式协议增量"累积成"text_parts / tool_calls / thinking_segments / finish_reason"。
consume_stream 既 yield 思考/正文事件，又通过 return 值回传累积结果（沿用生成器
返回值捕获：`result = yield from consume_stream(stream)`）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Iterator, Optional

from chorus.domain.events import (
    ReasoningDoneEvent,
    ReasoningEvent,
    SseEvent,
    TokenEvent,
)
from chorus.domain.trace import ThinkingSegment


@dataclass
class StreamResult:
    """一次流式响应的累积结果，由 TurnState.apply_stream 写入回合状态。"""

    text_parts: list[str] = field(default_factory=list)
    # index → {id, name, arguments}（按流式分片顺序合并的完整工具调用）
    tool_calls: dict[int, dict] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)


def consume_stream(stream) -> Iterator[SseEvent]:
    """消费 OpenAI 流式响应：yield 思考/正文事件并累积工具调用，return StreamResult。"""
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
            in_progress = False

        if delta.content:
            text_parts.append(delta.content)
            yield TokenEvent(content=delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                _merge_tool_call(accumulated, tc)

    if in_progress:
        duration = _close_thinking(cur_parts, started_at, thinking_segments)
        yield ReasoningDoneEvent(duration_ms=duration)

    return StreamResult(
        text_parts=text_parts,
        tool_calls=accumulated,
        finish_reason=finish_reason,
        thinking_segments=thinking_segments,
    )


def drain_stream(stream) -> StreamResult:
    """消费流式响应但丢弃 SSE 事件，仅返回累积 StreamResult（subagent 用，不连 SSE）。

    与 consume_stream 同逻辑（累积 text/tool_calls/thinking/finish_reason），但不 yield
    任何事件——subagent 后台线程不需要把 reasoning/token 推前端，只取最终结果。
    """
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

        if in_progress and (delta.content or delta.tool_calls):
            _close_thinking(cur_parts, started_at, thinking_segments)
            in_progress = False

        if delta.content:
            text_parts.append(delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                _merge_tool_call(accumulated, tc)

    if in_progress:
        _close_thinking(cur_parts, started_at, thinking_segments)

    return StreamResult(
        text_parts=text_parts,
        tool_calls=accumulated,
        finish_reason=finish_reason,
        thinking_segments=thinking_segments,
    )


def _close_thinking(
    parts: list[str], started_at: Optional[float], segments: list[ThinkingSegment]
) -> int:
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
