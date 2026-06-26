"""观测 hook：在 LLM 调用前后 / 工具执行前后写 trace 行并 yield TraceEvent。

原 TraceHook 逻辑去掉 Hook ABC，方法对齐 HookRegistry 事件点。各方法返回
Iterable[SseEvent] | None；经 trigger 调用时由 trigger 负责 fail-open。
payload 各 phase schema 见 repositories/trace.py 头注释。
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent, TraceEvent
from chorus.domain.trace import TraceEntry, TracePhase
from chorus.services.message import MessageService


class TraceEmitter:
    def __init__(self, message_service: MessageService, max_tokens: int):
        self._message = message_service
        self._max_tokens = max_tokens

    def before_model_request(self, ctx: AgentContext) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.MODEL_REQUEST, {
            "model": ctx.chat_model,
            "messages": ctx.turn.provider_messages or [],
            "tools": ctx.tool_schemas,
            "max_tokens": self._max_tokens,
        })]

    def after_model_response(self, ctx: AgentContext) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.MODEL_RESPONSE, self._response_payload(ctx))]

    def on_tool_call(
        self, ctx: AgentContext, call: dict, display: str, running_label: Any
    ) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.TOOL_CALL, {
            "id": call["id"], "name": call["name"], "arguments": call["arguments"],
            "display": display, "running_label": running_label,
        })]

    def on_tool_result(self, ctx: AgentContext, call: dict, result: Any) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.TOOL_RESULT, {
            "tool_call_id": call["id"], "name": call["name"],
            "content": result.outcome.content, "duration_ms": result.duration_ms,
        })]

    def _emit(self, ctx: AgentContext, phase: TracePhase, payload: dict) -> SseEvent:
        ts = time.time()
        self._message.add_trace(TraceEntry(
            session_id=ctx.session_id,
            message_id=ctx.turn.message_id or None,
            source=ctx.source,
            task_id=ctx.task_id,
            iteration=ctx.turn.iteration_index,
            phase=phase, ts=ts, payload=payload,
        ))
        return TraceEvent(
            phase=phase, iteration=ctx.turn.iteration_index,
            message_id=ctx.turn.message_id or None, ts=ts, payload=payload,
        )

    @staticmethod
    def _response_payload(ctx: AgentContext) -> dict:
        accumulated = ctx.turn.accumulated_tool_calls or {}
        tool_calls = [
            {"id": e["id"], "name": e["name"], "arguments": e["arguments"]}
            for _, e in sorted(accumulated.items())
        ]
        return {
            "content": "".join(ctx.turn.text_parts or []),
            "finish_reason": ctx.turn.finish_reason,
            "tool_calls": tool_calls,
            "thinking_segments": [s.model_dump() for s in ctx.turn.thinking_segments],
        }
