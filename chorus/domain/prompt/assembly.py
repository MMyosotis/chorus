"""系统提示词装配入口：基础文案加条件段，按原料拼成完整提示词。

技能段是否拼入由白名单是否含加载工具决定；新增条件段在此扩展。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from chorus.domain.intent import IntentState

if TYPE_CHECKING:
    from chorus.domain.skill import SkillLoader


@dataclass(frozen=True)
class PromptContext:
    """装配原料：基础文案与可选的意图快照、技能加载器。"""

    base: str
    intent_state: IntentState | None = None
    tool_names: tuple[str, ...] = ()
    skill_loader: "SkillLoader | None" = None


def build_system_prompt(ctx: PromptContext) -> str:
    parts = [ctx.base]
    section = _skill_section(ctx.tool_names, ctx.skill_loader)
    if section:
        parts.append(section)
    if ctx.intent_state is not None:
        parts.append(_intent_state_block(ctx.intent_state))
    return "\n\n".join(parts)


def _skill_section(tool_names: tuple[str, ...], skill_loader: "SkillLoader | None") -> str:
    """白名单含加载工具才产出技能清单，否则空串。"""
    if skill_loader is None or "load_skill" not in tool_names:
        return ""
    return skill_loader.format_hints()


def _intent_state_block(state: IntentState) -> str:
    payload = state.model_dump(
        mode="json",
        exclude={"session_id", "version", "updated_at"},
    )
    return (
        "## 当前意图状态\n"
        "下面是本会话最新的完整意图快照。基于它继续对话，"
        "未被用户修改的字段保持原值。update_intent_state 接收完整快照，不是增量补丁。\n"
        "<current_intent_state>\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "</current_intent_state>"
    )
