"""ToolCallsDetected hook：写 tool_calls 消息、执行工具、yield 事件、写 metadata。"""

import json
from time import perf_counter

from backend.hooks.manager import AgentContext
from backend.tools import dispatch_tool, format_tool_display, get_running_label


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

        yield {
            "type": "tool_call",
            "id": tc["id"],
            "name": tool_name,
            "arguments": tool_args,
            "display": display,
            "running_label": running_label,
        }

        t0 = perf_counter()
        result = dispatch_tool(tool_name, tool_args)
        duration_ms = int((perf_counter() - t0) * 1000)

        yield {
            "type": "tool_result",
            "tool_call_id": tc["id"],
            "name": tool_name,
            "content": result,
            "duration_ms": duration_ms,
        }

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
