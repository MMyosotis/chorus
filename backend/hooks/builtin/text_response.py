"""AssistantTextResponse hook：写 assistant 文本到 history、save、yield done。

注册顺序保证此 hook 先执行（先 yield done 让前端解锁），title hook 其后。
"""

import time

from backend.hooks.manager import AgentContext


def on_assistant_text_response(ctx: AgentContext):
    full_text = "".join(ctx.text_parts or [])
    if full_text:
        ctx.conv["history"].append({
            "role": "assistant",
            "content": full_text,
            "_meta_message_id": ctx.message_id,
        })
    ctx.conv["updated_at"] = time.time()
    ctx.store.save(ctx.conversation_id)
    return [{"type": "done"}]
