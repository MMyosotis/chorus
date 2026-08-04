"""SSE 事件模型：按类型区分的封闭联合，序列化后推给前端。"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.trace import TracePhase


class _EventBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MessageStartEvent(_EventBase):
    type: Literal["message_start"] = "message_start"
    id: str


class ReasoningEvent(_EventBase):
    type: Literal["reasoning"] = "reasoning"
    content: str


class ReasoningDoneEvent(_EventBase):
    type: Literal["reasoning_done"] = "reasoning_done"
    duration_ms: int


class TokenEvent(_EventBase):
    type: Literal["token"] = "token"
    content: str


class ToolCallEvent(_EventBase):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    arguments: dict
    display: str
    running_label: Optional[str] = None


class ToolResultEvent(_EventBase):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    content: str
    duration_ms: int


class TraceEvent(_EventBase):
    type: Literal["trace"] = "trace"
    phase: TracePhase
    message_id: Optional[str] = None
    created_at: float
    payload: dict


class TitleUpdateEvent(_EventBase):
    type: Literal["title_update"] = "title_update"
    id: str
    title: str


class DoneEvent(_EventBase):
    type: Literal["done"] = "done"


class SuspendEvent(_EventBase):
    type: Literal["suspend"] = "suspend"


class ErrorEvent(_EventBase):
    type: Literal["error"] = "error"
    content: str


class BusyEvent(_EventBase):
    type: Literal["busy"] = "busy"
    content: str


class ArchivedEvent(_EventBase):
    type: Literal["archived"] = "archived"
    content: str


class IntentStateEvent(_EventBase):
    type: Literal["intent_state"] = "intent_state"
    state: dict


class OptionPromptEvent(_EventBase):
    type: Literal["option_prompt"] = "option_prompt"
    prompt_id: str
    message_id: Optional[str] = None
    questions: list[dict]


SseEvent = Annotated[
    Union[
        MessageStartEvent,
        ReasoningEvent,
        ReasoningDoneEvent,
        TokenEvent,
        ToolCallEvent,
        ToolResultEvent,
        TraceEvent,
        TitleUpdateEvent,
        DoneEvent,
        SuspendEvent,
        BusyEvent,
        ArchivedEvent,
        IntentStateEvent,
        OptionPromptEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
