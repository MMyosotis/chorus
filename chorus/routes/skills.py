"""技能文件路由：按技能名与相对路径读技能包子文件，供前端拉渲染外壳。

读不到（技能或文件不存在、越界、后缀不在白名单）一律 404。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from chorus.domain.skill import SkillLoader
from chorus.domain.skill.loader import SUFFIX_MEDIA_TYPES
from chorus.routes.providers import provide_skill_loader

router = APIRouter(prefix="/api/skills")


@router.get("/{name}/files/{path:path}")
def get_skill_file(
    name: str, path: str,
    skill_loader: SkillLoader = Depends(provide_skill_loader),
) -> PlainTextResponse:
    content = skill_loader.read_file(name, path)
    if content is None:
        raise HTTPException(status_code=404, detail="skill file not found")
    media_type = SUFFIX_MEDIA_TYPES.get(Path(path).suffix, "text/plain; charset=utf-8")
    return PlainTextResponse(content, media_type=media_type)
