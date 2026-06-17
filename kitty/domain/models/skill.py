"""Skill 模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SkillSummary(BaseModel):
    """注入 system prompt 的摘要。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str


class SkillContent(BaseModel):
    """load_skill 工具返回的完整内容。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    full_content: str
