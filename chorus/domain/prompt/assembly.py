"""系统提示词装配入口：基础文案加条件段，按原料拼成完整提示词。

技能段是否拼入由白名单是否含加载工具决定；新增条件段在此扩展。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chorus.domain.skill import SkillLoader


@dataclass(frozen=True)
class PromptContext:
    """装配原料：基础文案与可选的技能加载器。"""

    base: str
    tool_names: tuple[str, ...] = ()
    skill_loader: "SkillLoader | None" = None


def build_system_prompt(ctx: PromptContext) -> str:
    parts = [ctx.base]
    section = _skill_section(ctx.tool_names, ctx.skill_loader)
    if section:
        parts.append(section)
    return "\n\n".join(parts)


def _skill_section(tool_names: tuple[str, ...], skill_loader: "SkillLoader | None") -> str:
    """白名单含加载工具才产出技能清单，否则空串。"""
    if skill_loader is None or "load_skill" not in tool_names:
        return ""
    return skill_loader.format_hints()
