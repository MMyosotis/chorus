"""SkillService：发现、解析、缓存 skill markdown（替代旧 SkillLoader 单例）。

扫描 skills_dir 下的 */SKILL.md，解析 frontmatter（name / description），
提供摘要（注入 system prompt）与完整内容（load_skill 工具）。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from kitty.domain.models.skill import SkillContent, SkillSummary


class SkillService:
    def __init__(self, skills_dir: Path):
        self._dir = Path(skills_dir)
        self._cache: dict[str, SkillContent] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            self._load_locked()

    def list_summaries(self) -> list[SkillSummary]:
        self._ensure_loaded()
        with self._lock:
            return [
                SkillSummary(name=s.name, description=s.description)
                for s in self._cache.values()
            ]

    def get(self, name: str) -> Optional[SkillContent]:
        self._ensure_loaded()
        with self._lock:
            return self._cache.get(name)

    def format_hints(self) -> str:
        """生成简短摘要，用于注入 system prompt。"""
        summaries = self.list_summaries()
        if not summaries:
            return ""
        lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
        for s in summaries:
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._cache.clear()
        if self._dir.exists():
            for path in sorted(self._dir.glob("*/SKILL.md")):
                skill = self._parse_file(path)
                if skill is not None:
                    self._cache[skill.name] = skill
        self._loaded = True

    @staticmethod
    def _parse_file(path: Path) -> Optional[SkillContent]:
        text = path.read_text(encoding="utf-8")
        name = path.parent.name
        description = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                name, description = SkillService._parse_frontmatter(parts[1], name)
        return SkillContent(name=name, description=description, full_content=text)

    @staticmethod
    def _parse_frontmatter(frontmatter: str, fallback_name: str) -> tuple[str, str]:
        name = fallback_name
        description = ""
        for line in frontmatter.strip().splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if key == "name":
                name = val
            elif key == "description":
                description = val
        return name, description
