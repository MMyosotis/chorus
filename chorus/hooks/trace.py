"""观测钩子：在模型调用与工具执行前后写轨迹并发出事件。"""

from __future__ import annotations

from typing import Any, Iterable

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent, TraceEvent
from chorus.domain.stream import parse_tool_arguments
from chorus.domain.trace import (
    ModelRequest,
    ModelResponse,
    TracePhase,
    TracePayload,
    TraceToolCall,
    TraceToolResult,
)
from chorus.services.trace import TraceService
from chorus.tools import ToolDispatch


class TraceEmitter:
    def __init__(self, trace_service: TraceService, dispatcher: ToolDispatch, max_tokens: int):
        self._trace = trace_service
        self._dispatcher = dispatcher
        self._max_tokens = max_tokens

    def before_model_request(self, ctx: AgentContext) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.MODEL_REQUEST, ModelRequest(
            model=ctx.chat_model,
            messages=ctx.turn.provider_messages or [],
            tools=ctx.tool_schemas,
            max_tokens=self._max_tokens,
        ))]

    def after_model_response(self, ctx: AgentContext) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.MODEL_RESPONSE, self._response_payload(ctx))]

    def on_tool_call(self, ctx: AgentContext, call: dict) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.TOOL_CALL, TraceToolCall(
            tool_call_id=call["id"], name=call["name"], arguments=call["arguments"],
            display=self._dispatcher.format_display(call["name"], call["arguments"]),
            running_label=self._dispatcher.running_label(call["name"]),
        ))]

    def on_tool_result(self, ctx: AgentContext, call: dict, result: Any) -> Iterable[SseEvent]:
        return [self._emit(ctx, TracePhase.TOOL_RESULT, TraceToolResult(
            tool_call_id=call["id"], name=call["name"],
            content=result.outcome.content, duration_ms=result.duration_ms,
        ))]

    def _emit(self, ctx: AgentContext, phase: TracePhase, payload: TracePayload) -> SseEvent:
        created_at = self._trace.add_trace(
            session_id=ctx.session_id,
            message_id=ctx.turn.message_id or None,
            source=ctx.source,
            task_id=ctx.task_id,
            phase=phase,
            payload=payload,
        )
        return TraceEvent(
            phase=phase,
            message_id=ctx.turn.message_id or None, created_at=created_at,
            payload=payload.model_dump(),
        )

    @staticmethod
    def _response_payload(ctx: AgentContext) -> ModelResponse:
        accumulated = ctx.turn.accumulated_tool_calls or {}
        tool_calls = [
            {"tool_call_id": e.id, "name": e.name, "arguments": parse_tool_arguments(e.arguments)}
            for _, e in sorted(accumulated.items())
        ]
        return ModelResponse(
            content="".join(ctx.turn.text_parts or []),
            finish_reason=ctx.turn.finish_reason,
            tool_calls=tool_calls,
            thinking_segments=list(ctx.turn.thinking_segments or []),
        )
