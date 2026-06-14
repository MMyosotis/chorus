"""Trace hook：在 LLM 调用前后 yield trace SSE 事件，给前端控制台展示。

事件 schema:
    {
        "type": "trace",
        "phase": "model_request" | "model_response" | "loop_end",
        "iteration": int,
        "message_id": str,
        "ts": float,             # time.time()
        "payload": dict,
    }

注册顺序约束（见 backend/hooks/builtin/__init__.py）：
- BeforeModelRequest:  sanitizer 先（生成 provider_messages），trace 后（读取它）
- AssistantTextResponse / ToolCallsDetected:  trace 先，业务 hook 后（trace 事件先到达前端）
"""

import time

from backend.config import MAX_TOKENS, MODEL_ID
from backend.hooks.manager import AgentContext


def _emit(phase: str, ctx: AgentContext, payload: dict) -> dict:
    return {
        "type": "trace",
        "phase": phase,
        "iteration": ctx.iteration_index,
        "message_id": ctx.message_id,
        "ts": time.time(),
        "payload": payload,
    }


def _build_response_payload(ctx: AgentContext) -> dict:
    accumulated = ctx.accumulated_tool_calls or {}
    tool_calls = [
        {"id": e["id"], "name": e["name"], "arguments": e["arguments"]}
        for _, e in sorted(accumulated.items())
    ]
    return {
        "content": "".join(ctx.text_parts or []),
        "finish_reason": ctx.finish_reason,
        "tool_calls": tool_calls,
        "thinking_segments": ctx.thinking_segments or [],
    }


def on_trace_before_model_request(ctx: AgentContext):
    yield _emit("model_request", ctx, {
        "model": MODEL_ID,
        "messages": ctx.provider_messages or [],
        "tools": ctx.tool_schemas,
        "max_tokens": MAX_TOKENS,
    })


def on_trace_assistant_text_response(ctx: AgentContext):
    yield _emit("model_response", ctx, _build_response_payload(ctx))


def on_trace_tool_calls_detected(ctx: AgentContext):
    yield _emit("model_response", ctx, _build_response_payload(ctx))


def on_trace_loop_end(ctx: AgentContext):
    if ctx.done_reason == "max_iterations_reached":
        yield _emit("loop_end", ctx, {"reason": ctx.done_reason})
