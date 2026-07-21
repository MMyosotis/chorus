"""Skill 加载器：发现并解析 skill markdown，每次现扫现解析、不缓存。

读取低频，重扫成本可忽略；开发期改技能即时生效。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chorus.domain.skill.models import SkillContent, SkillSummary


SKILLS_DIR = Path(__file__).resolve().parents[2] / "resources" / "skills"

SUFFIX_MEDIA_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".yaml": "text/yaml; charset=utf-8",
}


class SkillLoader:
    """发现并解析技能文件，提供摘要、完整内容与子文件读取。"""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self._dir = Path(skills_dir)

    def list_summaries(self) -> list[SkillSummary]:
        return [SkillSummary(name=skill.name, description=skill.description) for skill, _ in self._scan_pairs()]

    def get(self, name: str) -> Optional[SkillContent]:
        return next((skill for skill, _ in self._scan_pairs() if skill.name == name), None)

    def list_files(self, name: str) -> Optional[list[str]]:
        """返回技能包内全部文件相对路径，无此技能返 None。"""
        skill_dir = next((d for skill, d in self._scan_pairs() if skill.name == name), None)
        if skill_dir is None:
            return None
        root = skill_dir.resolve()
        return [str(p.resolve().relative_to(root)) for p in sorted(root.rglob("*")) if p.is_file()]

    def read_file(self, name: str, rel_path: str) -> Optional[str]:
        """读技能包内子文件，越界逃逸或后缀不在白名单时返 None。"""
        skill_dir = next((d for skill, d in self._scan_pairs() if skill.name == name), None)
        if skill_dir is None:
            return None
        root = skill_dir.resolve()
        target = (skill_dir / rel_path).resolve()
        if not target.is_relative_to(root):
            return None
        if target.suffix not in SUFFIX_MEDIA_TYPES:
            return None
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def format_hints(self) -> str:
        """把摘要拼成 system prompt 技能段，无技能时返回空串。"""
        summaries = self.list_summaries()
        if not summaries:
            return ""
        lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
        for skill in summaries:
            lines.append(f"- **{skill.name}**: {skill.description}")
        return "\n".join(lines)

    def _scan_pairs(self) -> list[tuple[SkillContent, Path]]:
        pairs = []
        for path in sorted(self._dir.glob("*/SKILL.md")):
            content = SkillContent.from_markdown(path.read_text(encoding="utf-8"), path.parent.name)
            pairs.append((content, path.parent))
        return pairs
