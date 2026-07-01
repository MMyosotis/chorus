"""Skill 加载器：发现并解析 skill markdown，每次现扫现解析、不缓存。

读取低频，重扫成本可忽略；开发期改技能即时生效。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chorus.domain.skill.models import SkillContent, SkillSummary


SKILLS_DIR = Path(__file__).resolve().parents[2] / "resources" / "skills"


class SkillLoader:
    """发现并解析技能文件，提供摘要与完整内容。"""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self._dir = Path(skills_dir)

    def list_summaries(self) -> list[SkillSummary]:
        return [SkillSummary(name=s.name, description=s.description) for s in self._scan()]

    def get(self, name: str) -> Optional[SkillContent]:
        return next((s for s in self._scan() if s.name == name), None)

    def format_hints(self) -> str:
        """把摘要拼成 system prompt 技能段，无技能时返回空串。"""
        summaries = self.list_summaries()
        if not summaries:
            return ""
        lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
        for s in summaries:
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)

    def _scan(self) -> list[SkillContent]:
        if not self._dir.exists():
            return []
        return [
            SkillContent.from_markdown(p.read_text(encoding="utf-8"), p.parent.name)
            for p in sorted(self._dir.glob("*/SKILL.md"))
        ]
