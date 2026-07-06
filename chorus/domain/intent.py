"""会话级意图状态：主 Agent 每轮维护的结构化工作记忆。"""

from __future__ import annotations

import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


IntentStatus = Literal[
    "empty",
    "capturing",
    "needs_clarification",
    "ready_to_confirm",
    "confirmed",
    "dispatched",
]

InteractionIntent = Literal[
    "smalltalk",
    "create_content",
    "clarify_existing",
    "modify_intent",
    "confirm_intent",
    "reject_intent",
    "cancel_task",
    "ask_status",
    "give_feedback",
]

NextAction = Literal[
    "reply_only",
    "ask_user",
    "wait_user_confirm",
    "create_plan_after_confirm",
    "dispatching",
    "blocked",
]


class ConfirmationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class ConfirmationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    items: list[ConfirmationItem] = Field(default_factory=list)


class IntentState(BaseModel):
    """最新意图快照，独立于 message history 存储。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    interaction_intent: InteractionIntent = "smalltalk"
    intent_status: IntentStatus = "empty"
    goal: str = ""
    known_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    confirmation_summary: Optional[ConfirmationSummary] = None
    next_action: NextAction = "reply_only"
    confidence: float = 0.0
    version: int = 0
    updated_at: float = Field(default_factory=time.time)

    def public_dict(self) -> dict:
        return self.model_dump(mode="json")


class IntentStatePatch(BaseModel):
    """update_intent_state 工具入参，session/version 由服务端补齐。"""

    model_config = ConfigDict(extra="forbid")

    interaction_intent: InteractionIntent
    intent_status: IntentStatus
    goal: str = ""
    known_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    confirmation_summary: Optional[ConfirmationSummary] = None
    next_action: NextAction
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def empty_intent_state(session_id: str) -> IntentState:
    return IntentState(session_id=session_id)
