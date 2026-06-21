"""Skill 加载器：发现、解析、缓存 skill markdown，并对外提供摘要。

扫盘 → 解析 → 内存缓存（线程安全、懒加载）→ 按 name 查找 / 取摘要。
format_skill_hints 是紧贴 loader 的纯操作，把摘要拼成 system prompt 技能段。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from kitty.domain.skill.models import SkillContent, SkillSummary

# 技能 markdown 资源目录：随源码版本管理（kitty/resources/skills）。
# 与 SkillLoader 同模块——它就是 loader 的默认扫描目录，参照 title.py 的 STORED_TITLE_MAX_LEN。
SKILLS_DIR = Path(__file__).resolve().parents[2] / "resources" / "skills"


def format_skill_hints(summaries: list[SkillSummary]) -> str:
    """生成 skill 摘要文本（作为 PromptContext.skill_hints 的来源），无技能时返回空串。"""
    if not summaries:
        return ""
    lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
    for s in summaries:
        lines.append(f"- **{s.name}**: {s.description}")
    return "\n".join(lines)


class SkillLoader:
    """发现、解析、缓存 skill markdown。

    扫描 skills_dir 下的 */SKILL.md，解析 frontmatter（name / description），
    提供摘要（注入 system prompt）与完整内容（load_skill 工具）。
    """

    def __init__(self, skills_dir: Path = SKILLS_DIR):
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

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._cache.clear()
        if self._dir.exists():
            for path in sorted(self._dir.glob("*/SKILL.md")):
                skill = SkillContent.from_markdown(
                    path.read_text(encoding="utf-8"), path.parent.name
                )
                self._cache[skill.name] = skill
        self._loaded = True
