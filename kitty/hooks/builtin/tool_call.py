"""ToolCallsDetected hook：写 assistant(tool_calls)、逐个执行工具、写 tool 消息、yield 事件。

每个 tool_call / tool_result 之前先写一条 trace 行（traces 表权威源）并 yield TraceEvent。
工具执行经注入的 ToolRegistry.dispatch（统一计时 / 包错 / display）。
"""

from __future__ import annotations

import json
import time
from typing import Iterable

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent, ToolCallEvent, ToolResultEvent, TraceEvent
from kitty.domain.models.message import ToolCallSpec
from kitty.domain.models.tool import ToolCall
from kitty.domain.models.trace import TraceEntry, TracePhase
from kitty.hooks.base import Hook
from kitty.services.session import SessionService
from kitty.tools.base import ToolContext, ToolCtxFactory, ToolRegistry


class ToolCallHook(Hook):
    def __init__(
        self,
        session_service: SessionService,
        tool_registry: ToolRegistry,
        tool_ctx_factory: ToolCtxFactory,
    ):
        self._session = session_service
        self._registry = tool_registry
        self._tool_ctx_factory = tool_ctx_factory

    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        tool_calls_list = self._materialize(ctx)
        self._append_assistant(ctx, tool_calls_list)
        tool_ctx = self._tool_ctx_factory(ctx.session_id)
        for tc in tool_calls_list:
            yield from self._run_one(ctx, tc, tool_ctx)

    # ------------------------------------------------------------------
    @staticmethod
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

    def _append_assistant(self, ctx: AgentContext, tool_calls_list: list[dict]) -> None:
        content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
        specs = [
            ToolCallSpec(id=tc["id"], name=tc["function"]["name"], arguments_json=tc["function"]["arguments"])
            for tc in tool_calls_list
        ]
        self._session.append_assistant_message(
            ctx.session_id, message_id=ctx.turn.message_id, content=content, tool_calls=specs,
        )

    def _run_one(self, ctx: AgentContext, tc: dict, tool_ctx: ToolContext) -> Iterable[SseEvent]:
        call = ToolCall(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=self._parse_args(tc["function"]["arguments"]),
        )
        display = self._registry.format_display(call.name, call.arguments)
        running_label = self._registry.running_label(call.name)

        yield self._trace(ctx, TracePhase.TOOL_CALL, {
            "id": call.id, "name": call.name, "arguments": call.arguments,
            "display": display, "running_label": running_label,
        })
        yield ToolCallEvent(
            id=call.id, name=call.name, arguments=call.arguments,
            display=display, running_label=running_label,
        )

        result = self._registry.dispatch(call, tool_ctx)
        self._session.append_tool_message(
            ctx.session_id, tool_call_id=call.id, name=call.name, content=result.content,
        )
        yield self._trace(ctx, TracePhase.TOOL_RESULT, {
            "tool_call_id": call.id, "name": call.name,
            "content": result.content, "duration_ms": result.duration_ms,
        })
        yield ToolResultEvent(
            tool_call_id=call.id, name=call.name,
            content=result.content, duration_ms=result.duration_ms,
        )

    @staticmethod
    def _parse_args(raw: str) -> dict:
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def _trace(self, ctx: AgentContext, phase: TracePhase, payload: dict) -> SseEvent:
        ts = time.time()
        self._session.add_trace(TraceEntry(
            session_id=ctx.session_id,
            message_id=ctx.turn.message_id or None,
            iteration=ctx.turn.iteration_index,
            phase=phase, ts=ts, payload=payload,
        ))
        return TraceEvent(
            phase=phase, iteration=ctx.turn.iteration_index,
            message_id=ctx.turn.message_id or None, ts=ts, payload=payload,
        )
