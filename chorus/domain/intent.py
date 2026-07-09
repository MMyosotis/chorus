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

# next_action 由 intent_status 派生，不让模型填，避免与 status 不自洽。
NextAction = Literal[
    "reply_only",
    "ask_user",
    "wait_user_confirm",
    "create_plan_after_confirm",
    "dispatching",
]

_STATUS_TO_NEXT_ACTION: dict[str, NextAction] = {
    "empty": "reply_only",
    "capturing": "ask_user",
    "needs_clarification": "ask_user",
    "ready_to_confirm": "wait_user_confirm",
    "confirmed": "create_plan_after_confirm",
    "dispatched": "dispatching",
}


def derive_next_action(status: str) -> NextAction:
    """从意图成熟度派生下一步动作，单一映射集中维护。"""
    return _STATUS_TO_NEXT_ACTION.get(status, "reply_only")


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
    intent_status: IntentStatus = "empty"
    goal: str = ""
    known_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    confirmation_summary: Optional[ConfirmationSummary] = None
    version: int = 0
    updated_at: float = Field(default_factory=time.time)

    def public_dict(self) -> dict:
        """对外视图：含派生 next_action，供前端展示与 prompt 注入。"""
        data = self.model_dump(mode="json")
        data["next_action"] = derive_next_action(self.intent_status)
        return data


class IntentStatePatch(BaseModel):
    """update_intent_state 工具入参，session/version 由服务端补齐。"""

    model_config = ConfigDict(extra="forbid")

    intent_status: IntentStatus
    goal: str = ""
    known_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    confirmation_summary: Optional[ConfirmationSummary] = None
    friendly_reply: Optional[str] = None


def empty_intent_state(session_id: str) -> IntentState:
    return IntentState(session_id=session_id)
