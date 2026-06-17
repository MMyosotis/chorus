"""SystemPromptBuilder：拼装 system prompt（基础提示 + skill 摘要）。

system 消息不持久化，每次对话开始由本类现拼（延续现状）。
"""

from __future__ import annotations

from kitty.services.skill import SkillService


class SystemPromptBuilder:
    def __init__(self, base_prompt: str, skill_service: SkillService):
        self._base = base_prompt
        self._skills = skill_service

    def build(self) -> str:
        hints = self._skills.format_hints()
        if not hints:
            return self._base
        return self._base + "\n\n" + hints
