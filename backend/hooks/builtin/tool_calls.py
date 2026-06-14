"""ToolCallsDetected hook：写 tool_calls 消息、执行工具、yield 事件、写 metadata。

每个 tool_call / tool_result SSE 事件之前会先 yield 一条 type=trace 事件并写库，
作为后端权威 trace 源（前端不再合成）。
"""

import json
import time
from time import perf_counter

from backend.hooks.manager import AgentContext
from backend.tools import dispatch_tool, format_tool_display, get_running_label


def _emit_trace(ctx: AgentContext, phase: str, payload: dict) -> dict:
    ts = time.time()
    try:
        ctx.store.add_trace(
            ctx.conversation_id,
            phase,
            payload,
            iteration=ctx.iteration_index,
            message_id=ctx.message_id,
            ts=ts,
        )
    except Exception:
        pass
    return {
        "type": "trace",
        "phase": phase,
        "iteration": ctx.iteration_index,
        "message_id": ctx.message_id,
        "ts": ts,
        "payload": payload,
    }


def on_tool_calls_detected(ctx: AgentContext):
    accumulated = ctx.accumulated_tool_calls or {}
    tool_calls_list = [
        {
            "id": e["id"],
            "type": "function",
            "function": {"name": e["name"], "arguments": e["arguments"]},
        }
        for _, e in sorted(accumulated.items())
    ]

    ctx.conv["history"].append({
        "role": "assistant",
        "content": "".join(ctx.text_parts or []) or None,
        "tool_calls": tool_calls_list,
        "_meta_message_id": ctx.message_id,
    })

    # ctx.msg_meta 已由 IterationStart hook 初始化
    msg_meta = ctx.msg_meta
    if msg_meta is None:
        msg_meta = ctx.conv["assistant_messages"].setdefault(
            ctx.message_id, {"thinking": [], "tools": []}
        )

    for tc in tool_calls_list:
        tool_name = tc["function"]["name"]
        try:
            tool_args = json.loads(tc["function"]["arguments"])
        except json.JSONDecodeError:
            tool_args = {}

        display = format_tool_display(tool_name, tool_args)
        running_label = get_running_label(tool_name)

        tool_call_event = {
            "type": "tool_call",
            "id": tc["id"],
            "name": tool_name,
            "arguments": tool_args,
            "display": display,
            "running_label": running_label,
        }
        yield _emit_trace(ctx, "tool_call", dict(tool_call_event))
        yield tool_call_event

        t0 = perf_counter()
        result = dispatch_tool(tool_name, tool_args)
        duration_ms = int((perf_counter() - t0) * 1000)

        tool_result_event = {
            "type": "tool_result",
            "tool_call_id": tc["id"],
            "name": tool_name,
            "content": result,
            "duration_ms": duration_ms,
        }
        yield _emit_trace(ctx, "tool_result", dict(tool_result_event))
        yield tool_result_event

        msg_meta["tools"].append({
            "name": tool_name,
            "arguments": tool_args,
            "duration_ms": duration_ms,
            "content": result,
            "display": display,
        })

        ctx.conv["history"].append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        })
