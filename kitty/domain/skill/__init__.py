"""Skill 领域：模型 + 加载器，围绕 skill 单一概念内聚。"""

from __future__ import annotations

from kitty.domain.skill.loader import SKILLS_DIR, SkillLoader, format_skill_hints
from kitty.domain.skill.models import SkillContent, SkillSummary

__all__ = [
    "SkillSummary",
    "SkillContent",
    "SkillLoader",
    "format_skill_hints",
    "SKILLS_DIR",
]
