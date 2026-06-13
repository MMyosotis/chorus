"""持久化 hook：工具分支轮末 save、max_iterations 兜底 save + done。"""

import time

from backend.hooks.manager import AgentContext


def on_iteration_end(ctx: AgentContext):
    """工具分支结束后保存。文本分支已经在 text_response hook 里 save 过并返回，
    所以这里只会在工具分支后被触发。"""
    ctx.conv["updated_at"] = time.time()
    ctx.store.save(ctx.conversation_id)
    return None


def on_loop_end(ctx: AgentContext):
    """达到 MAX_TOOL_ITERATIONS 时触发：保存并 yield done with reason。"""
    ctx.conv["updated_at"] = time.time()
    ctx.store.save(ctx.conversation_id)
    return [{"type": "done", "reason": ctx.done_reason or "max_iterations_reached"}]
