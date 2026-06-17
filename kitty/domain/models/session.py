"""会话元数据模型。仅描述 session 本身，不含消息与 trace ——
消息见 message.py，trace 见 trace.py，三者按 session_id / message_id 关联。
"""

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
    """list 接口返回的精简视图，省略 title_generated 等内部字段。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    created_at: float
    updated_at: float
