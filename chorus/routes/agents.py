"""角色档案路由。

暴露 AGENT_PROFILES 的前端可见部分（display_name / enter_line）给流水线渲染。
enter_line 是静态文案，后端 AGENT_PROFILES 是唯一来源，前端启动拉一次缓存。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from chorus.domain.task import AGENT_PROFILES

router = APIRouter(prefix="/api/agents")


class ProfileView(BaseModel):
    display_name: str
    enter_line: str


@router.get("/profiles", response_model=dict[str, ProfileView])
def get_profiles():
    # 仅暴露前端展示用字段；role_desc / artifacts_model / artifacts_schema 是后端内部细节，不外露
    return {
        agent_type: ProfileView(
            display_name=p.display_name,
            enter_line=p.enter_line,
        )
        for agent_type, p in AGENT_PROFILES.items()
    }
