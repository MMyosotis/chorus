from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    full_content: str = ""


class SkillLoader:
    """发现、解析、缓存 skill markdown 文件。"""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self._cache: dict[str, Skill] = {}
        self._loaded = False

    def _load_all(self):
        if self._loaded:
            return
        if not self._skills_dir.exists():
            self._loaded = True
            return
        for path in sorted(self._skills_dir.glob("*/SKILL.md")):
            skill = self._parse_file(path)
            if skill:
                self._cache[skill.name] = skill
        self._loaded = True

    @staticmethod
    def _parse_file(path: Path) -> Optional[Skill]:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return Skill(
                name=path.parent.name,
                description="",
                full_content=text,
            )
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        frontmatter = parts[1].strip()
        meta: dict = {}
        for line in frontmatter.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip()
        return Skill(
            name=meta.get("name", path.parent.name),
            description=meta.get("description", ""),
            full_content=text,
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        self._load_all()
        return self._cache.get(name)

    def list_names(self) -> list[str]:
        self._load_all()
        return list(self._cache.keys())

    def format_skill_hints(self) -> str:
        """生成简短摘要，用于注入 system prompt。"""
        self._load_all()
        if not self._cache:
            return ""
        lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
        for s in self._cache.values():
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)
