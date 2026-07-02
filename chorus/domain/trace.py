"""轨迹模型：隶属于消息的执行轨迹，独立存储。

靠消息标识关联消息，物理解耦。一条轨迹是一个阶段快照，思考段与工具摘要由若干行聚合得到。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TracePhase(str, Enum):
    """轨迹行阶段，载荷结构由阶段决定。"""

    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SCHEDULE = "schedule"


class ThinkingSegment(BaseModel):
    """一段连续的思考过程。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    duration_ms: int


class ToolInvocation(BaseModel):
    """一次工具调用的展示摘要。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_call_id: str
    name: str
    arguments: dict
    display: str
    duration_ms: int
    content: str


class TraceEntry(BaseModel):
    """traces 表的一行。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Optional[int] = None
    session_id: str
    message_id: Optional[str] = None
    task_id: Optional[str] = None
    source: str = "supervisor"
    phase: TracePhase
    created_at: float
    payload: dict


class MessageTrace(BaseModel):
    """聚合视图：助手消息关联的思考与工具摘要，由若干轨迹行重建。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)
