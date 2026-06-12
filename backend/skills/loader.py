from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
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
        for path in sorted(self._skills_dir.glob("*.md")):
            skill = self._parse_file(path)
            if skill:
                self._cache[skill.name] = skill
        self._loaded = True

    @staticmethod
    def _parse_file(path: Path) -> Optional[Skill]:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            # 无 frontmatter，用文件名做 name
            return Skill(
                name=path.stem,
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
                key = key.strip()
                val = val.strip()
                if val.startswith("[") and val.endswith("]"):
                    val = [
                        t.strip().strip("'\"")
                        for t in val[1:-1].split(",")
                        if t.strip()
                    ]
                meta[key] = val
        name = meta.get("name", path.stem)
        description = meta.get("description", "")
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        return Skill(
            name=name,
            description=description,
            tags=tags,
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
        lines = ["## Available Skills (use load_skill to get full details)"]
        for s in self._cache.values():
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)
