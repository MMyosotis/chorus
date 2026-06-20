"""Trace hook：在 LLM 调用前后写 trace 行（traces 表）并 yield TraceEvent 给前端控制台。

payload 各 phase schema 见 repositories/trace.py 头注释。
触发顺序（见 HookManager 各具名方法的字面顺序）：sanitizer 先于 trace（trace 读
provider_messages）；trace 先于业务 hook（trace 事件先到达前端）。
"""

from __future__ import annotations

import time
from typing import Iterable

from kitty.domain.agent import AgentContext
from kitty.domain.events import SseEvent, TraceEvent
from kitty.domain.trace import TraceEntry, TracePhase
from kitty.hooks.base import Hook
from kitty.services.session import SessionService


class TraceHook(Hook):
    def __init__(self, session_service: SessionService, model_id: str, max_tokens: int):
        self._session = session_service
        self._model = model_id
        self._max_tokens = max_tokens

    def before_model_request(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        return [self._emit(ctx, TracePhase.MODEL_REQUEST, {
            "model": self._model,
            "messages": ctx.turn.provider_messages or [],
            "tools": ctx.tool_schemas,
            "max_tokens": self._max_tokens,
        })]

    def assistant_text_response(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        return [self._emit(ctx, TracePhase.MODEL_RESPONSE, self._response_payload(ctx))]

    def tool_calls_detected(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        return [self._emit(ctx, TracePhase.MODEL_RESPONSE, self._response_payload(ctx))]

    def loop_end(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        if ctx.outcome.done_reason:
            return [self._emit(ctx, TracePhase.LOOP_END, {"reason": ctx.outcome.done_reason})]
        return None

    # ------------------------------------------------------------------
    def _emit(self, ctx: AgentContext, phase: TracePhase, payload: dict) -> SseEvent:
        ts = time.time()
        self._session.add_trace(TraceEntry(
            session_id=ctx.session_id,
            message_id=ctx.turn.message_id or None,
            iteration=ctx.turn.iteration_index,
            phase=phase,
            ts=ts,
            payload=payload,
        ))
        return TraceEvent(
            phase=phase,
            iteration=ctx.turn.iteration_index,
            message_id=ctx.turn.message_id or None,
            ts=ts,
            payload=payload,
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
