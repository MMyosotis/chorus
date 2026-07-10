"""流式响应消费：把流式增量累积成领域状态并发出事件。

纯变换，零副作用。边发出思考与正文事件，边通过返回值回传累积结果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Generator, Optional

from chorus.domain.events import (
    ReasoningDoneEvent,
    ReasoningEvent,
    SseEvent,
    TokenEvent,
)
from chorus.domain.trace import ThinkingSegment


@dataclass
class ToolCallAccumulator:
    """工具调用分片累积盒，跨分片按序归拢拼装。"""

    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class StreamResult:
    """一次流式响应的累积结果。"""

    text_parts: list[str] = field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)


def parse_tool_arguments(raw: str) -> dict:
    """把累积的 JSON 字符串解析为 dict。

    流式分片拼出的是字符串，空串或非法 JSON 降级为空 dict，供工具调用参数与 trace 摘要复用。
    """
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _accumulate(stream) -> Generator[SseEvent, None, StreamResult]:
    """逐块累积，发出思考与正文事件，返回累积结果。"""
    accumulated: dict[int, ToolCallAccumulator] = {}
    text_parts: list[str] = []
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = []

    cur_parts: list[str] = []
    started_at: Optional[float] = None

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta
        if choice.finish_reason is not None:
            finish_reason = choice.finish_reason

        reasoning: Optional[str] = getattr(delta, "reasoning_content", None)
        if reasoning:
            if started_at is None:
                started_at = perf_counter()
            cur_parts.append(reasoning)
            yield ReasoningEvent(content=reasoning)

        # 思考结束出现正文
        if started_at is not None and (delta.content or delta.tool_calls):
            duration = _close_thinking(cur_parts, started_at, thinking_segments)
            yield ReasoningDoneEvent(duration_ms=duration)
            started_at = None

        if delta.content:
            text_parts.append(delta.content)
            yield TokenEvent(content=delta.content)

        if delta.tool_calls:
            for call in delta.tool_calls:
                _merge_tool_call(accumulated, call)

    # 处理只有思考没有正文场景
    if started_at is not None:
        duration = _close_thinking(cur_parts, started_at, thinking_segments)
        yield ReasoningDoneEvent(duration_ms=duration)

    return StreamResult(
        text_parts=text_parts,
        tool_calls=accumulated,
        finish_reason=finish_reason,
        thinking_segments=thinking_segments,
    )


def consume_stream(stream) -> Generator[SseEvent, None, StreamResult]:
    """消费流式响应，发出思考与正文事件，返回累积结果。"""
    return (yield from _accumulate(stream))


def silent_consume(stream, on_token=lambda content: None) -> Generator[SseEvent, None, StreamResult]:
    """静默消费，正文 token 经回调透出，返回累积结果。"""
    gen = _accumulate(stream)
    while True:
        try:
            event = next(gen)
        except StopIteration as stop:
            return stop.value
        yield event
        if isinstance(event, TokenEvent):
            on_token(event.content)


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


def _merge_tool_call(accumulated: dict[int, ToolCallAccumulator], delta) -> None:
    """合并工具调用分片，按序号归拢拼装。"""
    index = delta.index
    entry = accumulated.get(index)
    if entry is None:
        entry = ToolCallAccumulator()
        accumulated[index] = entry

    # 工具首包带标识，将其与序号绑定，后续包只有序号
    if delta.id:
        entry.id = delta.id

    if delta.function:
        if delta.function.name:
            entry.name = delta.function.name
        if delta.function.arguments:
            entry.arguments += delta.function.arguments
