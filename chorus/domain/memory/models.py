"""创作者记忆领域模型：跨会话档案条目与角色可见目录摘要。"""
from __future__ import annotations

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
    updated_at: float


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
