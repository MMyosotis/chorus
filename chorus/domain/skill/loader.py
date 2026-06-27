"""Skill 加载器：发现、解析 skill markdown，无状态现扫现解析。

skills 数量少、文件小、读取低频（supervisor 每轮对话一次），重扫成本可忽略，
故不做内存缓存——每次调用现扫 ``*/SKILL.md`` 现解析。开发期改 skill 立即生效。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chorus.domain.skill.models import SkillContent, SkillSummary


SKILLS_DIR = Path(__file__).resolve().parents[2] / "resources" / "skills"


class SkillLoader:
    """发现、解析 skill markdown：扫描 skills_dir 下 */SKILL.md，解析 frontmatter
    （name / description），提供摘要（注入 system prompt）与完整内容（load_skill 工具）。"""

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
