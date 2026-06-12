from pathlib import Path

from backend.skills.loader import SkillLoader

from typing import Optional

_loader: Optional[SkillLoader] = None


def init_skill_loader(skills_dir: Path):
    global _loader
    _loader = SkillLoader(skills_dir)


def get_skill_loader() -> SkillLoader:
    if _loader is None:
        raise RuntimeError("SkillLoader not initialized. Call init_skill_loader() first.")
    return _loader
