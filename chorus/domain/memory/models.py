"""创作者记忆领域模型：跨会话档案条目与角色可见目录摘要。"""
from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["performance", "reference"]


class CreatorMemory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Kind = "reference"
    description: str
    content: str
    platform: list[str] = Field(default_factory=list)
    visible_to: list[str] = Field(default_factory=list)
    created_at: float


class MemoryDigestEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    platform: list[str] = Field(default_factory=list)
    kind: Kind = "reference"


class MemoryDigest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: list[MemoryDigestEntry] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.entries


class MemoryDraft(BaseModel):
    """LLM 产出的记忆草稿：整理时带时间戳保留原时间，提取时无时间戳由编排层补全。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Kind = "reference"
    description: str
    content: str
    platform: list[str] = Field(default_factory=list)
    visible_to: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None


def draft_to_memory(draft: MemoryDraft) -> CreatorMemory:
    """草稿转正式记忆；LLM 时间缺失或解析失败用当前时间。"""
    created_at = time.time()
    if draft.created_at:
        try:
            created_at = time.mktime(time.strptime(draft.created_at, "%Y-%m-%d %H:%M"))
        except (ValueError, TypeError):
            pass
    return CreatorMemory(
        id=uuid.uuid4().hex,
        kind=draft.kind,
        description=draft.description,
        content=draft.content,
        platform=draft.platform,
        visible_to=draft.visible_to,
        created_at=created_at,
    )
