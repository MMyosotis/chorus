"""Trace 模型：隶属于某条 message 的执行轨迹，独立于 message 存储。

traces 表只靠 message_id 关联 message，物理解耦；一条 trace = 一个 phase 的快照
（model_request / model_response / tool_call / tool_result）；
thinking 段与 tool 调用摘要通过对某 message_id 的若干 trace 行聚合得到。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TracePhase(str, Enum):
    """trace 行的阶段。payload 的 schema 由 phase 决定（见 TraceRepository 头注释）。"""

    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SCHEDULE = "schedule"  # 新增：scheduler 派发/CAS/zombie 事件


class ThinkingSegment(BaseModel):
    """一段连续的思考过程。

    seq 是与 ToolInvocation 共享的全局时序序号（单次响应内按真实发生顺序递增），
    供前端按 seq 交错还原 thinking↔tools 真实顺序；回放历史时不再被强制重排。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    duration_ms: int
    seq: int = 0


class ToolInvocation(BaseModel):
    """一次工具调用的展示摘要（给前端折叠面板用）。

    seq 与 ThinkingSegment 共享同一时序序号（见 ThinkingSegment.seq 说明）。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_call_id: str
    name: str
    arguments: dict
    display: str
    duration_ms: int
    content: str
    seq: int = 0


class TraceEntry(BaseModel):
    """traces 表的一行。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Optional[int] = None
    session_id: str
    message_id: Optional[str] = None
    task_id: Optional[str] = None      # 新增：subagent/scheduler trace 填此
    source: str = "supervisor"         # 新增：'supervisor'|'subagent'|'scheduler'
    iteration: Optional[int] = None
    phase: TracePhase
    ts: float
    payload: dict


class MessageTrace(BaseModel):
    """聚合视图：某条 assistant message 关联的 thinking + tools。

    由 TraceRepository.aggregate_message_trace(message_id) 从若干 TraceEntry 重建。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)
