"""LoopStart hook：注入 system prompt（含 skill 摘要），追加用户消息。"""

from backend.config import SYSTEM_PROMPT
from backend.hooks.manager import AgentContext


def _build_system_prompt() -> str:
    prompt = SYSTEM_PROMPT
    try:
        from backend.skills import get_skill_loader

        loader = get_skill_loader()
        hints = loader.format_skill_hints()
        if hints:
            prompt += "\n\n" + hints
    except RuntimeError:
        pass
    return prompt


def _ensure_system_prompt(conv: dict) -> None:
    history = conv["history"]
    sp = _build_system_prompt()
    if history and history[0].get("role") == "system":
        history[0]["content"] = sp
    else:
        history.insert(0, {"role": "system", "content": sp})


def on_loop_start(ctx: AgentContext):
    _ensure_system_prompt(ctx.conv)
    # history_snapshot_len 已在 ctx 构造时记录，对应"追加 user 消息之前"的位置。
    ctx.conv["history"].append({"role": "user", "content": ctx.user_message})
    return None
