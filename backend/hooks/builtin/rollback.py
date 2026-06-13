"""LoopError hook：回滚 history、清理 assistant_messages、save、yield error。"""

import time

from backend.hooks.manager import AgentContext


def on_loop_error(ctx: AgentContext):
    history = ctx.conv["history"]
    del history[ctx.history_snapshot_len:]
    for mid in ctx.new_message_ids:
        ctx.conv["assistant_messages"].pop(mid, None)
    try:
        ctx.conv["updated_at"] = time.time()
        ctx.store.save(ctx.conversation_id)
    except Exception:
        pass
    return [{"type": "error", "content": str(ctx.exception)}]
