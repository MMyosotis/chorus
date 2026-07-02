"""轨迹模型：隶属于消息的执行轨迹，独立存储。

靠消息标识关联消息，物理解耦。一条轨迹是一个阶段快照，思考段与工具摘要由若干行聚合得到。
每个阶段的载荷结构由对应模型强类型约束，入库 JSON 与读回还原经 phase 判别。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional, Union

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


class _PayloadBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModelRequest(_PayloadBase):
    """模型请求阶段载荷。"""

    model: str
    messages: list[dict]
    tools: list[dict]
    max_tokens: int


class ToolCallSummary(_PayloadBase):
    """模型响应里附带的一次工具调用摘要。"""

    tool_call_id: str
    name: str
    arguments: dict


class ModelResponse(_PayloadBase):
    """模型响应阶段载荷。"""

    content: str
    finish_reason: Optional[str] = None
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    thinking_segments: list[ThinkingSegment] = Field(default_factory=list)


class TraceToolCall(_PayloadBase):
    """工具调用阶段载荷。与 tools.models.ToolCall 同名故加 Trace 前缀消歧。"""

    tool_call_id: str
    name: str
    arguments: dict
    display: str
    running_label: Optional[str] = None


class TraceToolResult(_PayloadBase):
    """工具结果阶段载荷。与 TraceToolCall 成对，加 Trace 前缀保持一致。"""

    tool_call_id: str
    name: str
    content: str
    duration_ms: int


class Schedule(_PayloadBase):
    """调度事件阶段载荷（scheduler 派发/CAS 冲突/zombie 回收）。"""

    event: str
    task_id: str
    from_status: str
    to_status: str
    detail: str


TracePayload = Union[
    ModelRequest,
    ModelResponse,
    TraceToolCall,
    TraceToolResult,
    Schedule,
]


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
    payload: TracePayload


class MessageTrace(BaseModel):
    """聚合视图：助手消息关联的思考与工具摘要，由若干轨迹行重建。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)


@dataclass
class _FoldState:
    """聚合过程的累积状态。"""

    thinking: list[ThinkingSegment] = field(default_factory=list)
    tools: dict[str, ToolInvocation] = field(default_factory=dict)


def _fold_response(payload: ModelResponse, acc: _FoldState) -> None:
    acc.thinking.extend(payload.thinking_segments)


def _fold_tool_call(payload: TraceToolCall, acc: _FoldState) -> None:
    acc.tools[payload.tool_call_id] = ToolInvocation(
        tool_call_id=payload.tool_call_id, name=payload.name,
        arguments=payload.arguments, display=payload.display,
        duration_ms=0, content="",
    )


def _fold_tool_result(payload: TraceToolResult, acc: _FoldState) -> None:
    skeleton = acc.tools.setdefault(
        payload.tool_call_id,
        ToolInvocation(
            tool_call_id=payload.tool_call_id, name=payload.name,
            arguments={}, display="", duration_ms=0, content="",
        ),
    )
    acc.tools[payload.tool_call_id] = skeleton.model_copy(
        update={"duration_ms": payload.duration_ms, "content": payload.content},
    )


# payload 类型 → fold 函数注册表；未登记类型（ModelRequest/Schedule）自然 no-op
_FOLDERS: dict[type[TracePayload], Callable[..., None]] = {
    ModelResponse: _fold_response,
    TraceToolCall: _fold_tool_call,
    TraceToolResult: _fold_tool_result,
}


def aggregate_trace(message_id: str, entries: Iterable[TraceEntry]) -> MessageTrace:
    """从轨迹行重建思考与工具摘要：按 payload 类型查注册表分派。"""
    acc = _FoldState()
    for entry in entries:
        fn = _FOLDERS.get(type(entry.payload))
        if fn is not None:
            fn(entry.payload, acc)
    return MessageTrace(
        message_id=message_id,
        thinking=acc.thinking,
        tools=list(acc.tools.values()),
    )
