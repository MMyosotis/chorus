"""IterationStart hook：分配 message_id、初始化 msg_meta、yield message_start。"""

import uuid

from backend.hooks.manager import AgentContext


def on_iteration_start(ctx: AgentContext):
    message_id = uuid.uuid4().hex
    ctx.message_id = message_id
    ctx.new_message_ids.append(message_id)
    ctx.msg_meta = ctx.conv["assistant_messages"].setdefault(
        message_id, {"thinking": [], "tools": []}
    )
    return [{"type": "message_start", "id": message_id}]
