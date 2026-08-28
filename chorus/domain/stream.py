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
from chorus.domain.trace import ModelUsage, ThinkingSegment


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
    usage: Optional[ModelUsage] = None


class ThinkingTracker:
    """思考段开合盒：逐片喂入，非思考输出出现或流结束时收口。"""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._started_at: Optional[float] = None
        self.segments: list[ThinkingSegment] = []

    def feed(self, reasoning: str) -> ReasoningEvent:
        """喂入思考片，记录起始时刻并回吐事件。"""
        if self._started_at is None:
            self._started_at = perf_counter()
        self._parts.append(reasoning)
        return ReasoningEvent(content=reasoning)

    def close_if_open(self) -> Generator[ReasoningDoneEvent, None, None]:
        """有打开的思考段则收口并发事件，否则什么都不做。"""
        if self._started_at is None:
            return
        duration = int((perf_counter() - self._started_at) * 1000)
        self.segments.append(
            ThinkingSegment(text="".join(self._parts), duration_ms=duration)
        )
        self._parts.clear()
        self._started_at = None
        yield ReasoningDoneEvent(duration_ms=duration)


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


def _to_usage(raw) -> Optional[ModelUsage]:
    """把接口回传的原始用量转成领域用量，未回传则返回 None。"""
    if raw is None:
        return None
    return ModelUsage(
        input_tokens=raw.prompt_tokens,
        output_tokens=raw.completion_tokens,
        total_tokens=raw.total_tokens,
    )


def _accumulate(stream) -> Generator[SseEvent, None, StreamResult]:
    """逐块累积，发出思考与正文事件，返回累积结果。"""
    accumulated: dict[int, ToolCallAccumulator] = {}
    text_parts: list[str] = []
    finish_reason: Optional[str] = None
    thinking = ThinkingTracker()
    usage: Optional[ModelUsage] = None

    for chunk in stream:
        usage = _to_usage(chunk.usage)

        # 开启用量回传后，末块只带 usage、choices 为空
        if not chunk.choices:
            continue

        choice = chunk.choices[0]
        delta = choice.delta
        if choice.finish_reason is not None:
            finish_reason = choice.finish_reason

        reasoning: Optional[str] = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield thinking.feed(reasoning)

        # 非思考输出出现则收口当前思考段
        if delta.content or delta.tool_calls:
            yield from thinking.close_if_open()

        if delta.content:
            text_parts.append(delta.content)
            yield TokenEvent(content=delta.content)

        if delta.tool_calls:
            for call in delta.tool_calls:
                _merge_tool_call(accumulated, call)

    # 流结束兜底收口（只有思考没有正文场景）
    yield from thinking.close_if_open()

    return StreamResult(
        text_parts=text_parts,
        tool_calls=accumulated,
        finish_reason=finish_reason,
        thinking_segments=thinking.segments,
        usage=usage,
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
