"""会话元数据模型。仅描述会话本身，消息与轨迹另见它处。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Session(BaseModel):
    """一条会话的完整元数据（持久化在 sessions 表）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    title_generated: bool = False
    created_at: float
    updated_at: float


class SessionSummary(BaseModel):
    """列表接口的精简视图。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    created_at: float
    updated_at: float
