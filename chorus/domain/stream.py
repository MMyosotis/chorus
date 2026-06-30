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
class ToolCallAccumulator:
    """流式 tool_call 分片的累积盒：分片跨 chunk 到达，按 index 归拢后拼装。

    可变（流式期间反复 mutate）；id/name 首个非空分片即定、arguments 逐片拼接。
    """

    id: str = ""
    name: str = ""
    arguments: str = ""
    seq: int = 0


@dataclass
class StreamResult:
    """一次流式响应的累积结果，由 TurnState.apply_stream 写入回合状态。"""

    text_parts: list[str] = field(default_factory=list)
    # index → ToolCallAccumulator（按流式分片顺序合并的完整工具调用）
    tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)


def _accumulate(stream) -> Iterator[SseEvent]:
    """逐 chunk 累积：yield 思考/正文事件，return StreamResult（供 yield from 捕获返回值）。"""
    accumulated: dict[int, ToolCallAccumulator] = {}
    text_parts: list[str] = []
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = []
    seq_counter = 0  # thinking 段与 tool_call 共享的全局时序序号

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
            seq_counter += 1
            duration = _close_thinking(cur_parts, started_at, thinking_segments, seq_counter)
            yield ReasoningDoneEvent(duration_ms=duration)
            in_progress = False

        if delta.content:
            text_parts.append(delta.content)
            yield TokenEvent(content=delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                seq_counter = _merge_tool_call(accumulated, tc, seq_counter)

    if in_progress:
        seq_counter += 1
        duration = _close_thinking(cur_parts, started_at, thinking_segments, seq_counter)
        yield ReasoningDoneEvent(duration_ms=duration)

    return StreamResult(
        text_parts=text_parts,
        tool_calls=accumulated,
        finish_reason=finish_reason,
        thinking_segments=thinking_segments,
    )


def consume_stream(stream) -> Iterator[SseEvent]:
    """消费流式响应：yield 思考/正文事件，return StreamResult（supervisor SSE 用）。

    yield from 透传 _accumulate 的事件；其生成器返回值经 yield from 表达式的值回传给
    调用方（`result = yield from consume_stream(stream)` 捕获 StreamResult）。
    """
    return (yield from _accumulate(stream))


def drain_stream(stream) -> StreamResult:
    """消费流式响应但丢弃 SSE 事件，仅返回 StreamResult（subagent 用，不连 SSE）。

    与 consume_stream 共用 _accumulate（同累积逻辑），但不把 reasoning/token 推前端——
    subagent 后台线程只取最终结果。
    """
    gen = _accumulate(stream)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def _close_thinking(
    parts: list[str], started_at: Optional[float], segments: list[ThinkingSegment], seq: int
) -> int:
    if started_at is None:
        duration = 0
    else:
        duration = int((perf_counter() - started_at) * 1000)
    segments.append(ThinkingSegment(text="".join(parts), duration_ms=duration, seq=seq))
    parts.clear()
    return duration


def _merge_tool_call(accumulated: dict[int, ToolCallAccumulator], tc_delta, seq_counter: int) -> int:
    """合并流式 tool_call 分片。首次见到某 idx 时分配 seq（递增计数器回传），后续分片沿用。"""
    idx = tc_delta.index
    entry = accumulated.get(idx)
    if entry is None:
        seq_counter += 1
        entry = ToolCallAccumulator(seq=seq_counter)
        accumulated[idx] = entry
    if tc_delta.id:
        entry.id = tc_delta.id
    if tc_delta.function:
        if tc_delta.function.name:
            entry.name = tc_delta.function.name
        if tc_delta.function.arguments:
            entry.arguments += tc_delta.function.arguments
    return seq_counter
