"""系统提示词装配入口：基础文案加条件段，按原料拼成完整提示词。

系统段与用户回合段各持原料与注册表，新增段追加 renderer 即可。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from chorus.domain.intent import intent_state_block
from chorus.domain.memory import render_digest_block, render_recall_block

if TYPE_CHECKING:
    from chorus.domain.intent import IntentState
    from chorus.domain.memory import CreatorMemory, MemoryDigest
    from chorus.domain.skill import SkillLoader


@dataclass(frozen=True)
class PromptContext:
    """系统提示词原料：基础文案、技能加载器与记忆摘要。"""

    base: str
    skill_loader: "SkillLoader"
    memory_digest: "MemoryDigest"
    tool_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class UserMessageContext:
    """用户回合注入原料：可选的意图快照与召回记忆。"""

    intent_state: "IntentState | None" = None
    recalled_memories: list["CreatorMemory"] = field(default_factory=list)


def build_system_prompt(ctx: PromptContext) -> str:
    blocks = [ctx.base, *(render(ctx) for render in _SYSTEM_SECTIONS)]
    return "\n\n".join(filter(None, blocks))


def inject_user_blocks(msgs: list[dict], uctx: UserMessageContext) -> None:
    """各段拼到末条用户消息正文前，临时注入不入库；替换为拷贝，不动调用方持有的字典。"""
    text = "\n\n".join(block for block in (r(uctx) for r in _USER_SECTIONS) if block)
    if not text:
        return
    for index in range(len(msgs) - 1, -1, -1):
        if msgs[index]["role"] != "user":
            continue
        merged = text + "\n\n" + msgs[index]["content"]
        msgs[index] = {**msgs[index], "content": merged}
        return


def _skill_section(ctx: PromptContext) -> str:
    """白名单含加载工具才产出技能清单，否则空串。"""
    if "load_skill" not in ctx.tool_names:
        return ""
    return ctx.skill_loader.format_hints()


def _memory_section(ctx: PromptContext) -> str:
    return render_digest_block(ctx.memory_digest)


def _intent_section(uctx: UserMessageContext) -> str:
    """无意图快照返空串，否则建块注入（含 empty 状态）。"""
    if uctx.intent_state is None:
        return ""
    return intent_state_block(uctx.intent_state)


def _recall_section(uctx: UserMessageContext) -> str:
    return render_recall_block(uctx.recalled_memories)


_SYSTEM_SECTIONS: tuple = (_skill_section, _memory_section)
_USER_SECTIONS: tuple = (_recall_section, _intent_section)
