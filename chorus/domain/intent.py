"""会话级意图状态：主 Agent 每轮维护的结构化工作记忆。"""

from __future__ import annotations

import json
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


class Intent(BaseModel):
    """确认后用于执行的纯创作意图，不含会话状态。"""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field("", description="创作主题/方向")
    platform: str = Field("", description="目标平台展示名，如 网页博客")
    format: str = Field("", description="体裁，如 图文笔记/长文/短帖")
    style: str = Field("", description="风格倾向，如轻松/专业/种草")
    image_count: int = Field(description="配图数量")
    extra: dict[str, Any] = Field(default_factory=dict, description="其它要求/约束/受众等零散槽位（key 用中文短词，value 自然语言）")

    @classmethod
    def tool_schema_properties(cls, *names: str) -> dict:
        """从模型 Schema 中提取指定字段，供工具参数复用。"""
        model_properties = cls.model_json_schema()["properties"]
        selected = {}

        for name in names:
            field_schema = model_properties[name].copy()
            field_schema.pop("title", None)
            field_schema.pop("default", None)
            selected[name] = field_schema

        return selected


class IntentSnapshot(Intent):
    """主 Agent 对当前创作意图的完整理解。"""

    intent_status: IntentStatus = Field("empty", description="意图成熟度")
    progress_percent: int = Field(
        0,
        ge=0,
        le=100,
        description="意图信息完整度百分比，取 0 到 100 的整数；不是任务执行进度",
    )


class IntentStateUpdate(IntentSnapshot):
    """意图更新工具提交的完整快照。"""

    intent_status: IntentStatus


class IntentState(IntentSnapshot):
    """会话级意图状态，在快照上增加持久化身份与版本。"""

    session_id: str
    version: int = 0
    updated_at: float = Field(default_factory=time.time)

    @classmethod
    def from_update(cls, update: IntentStateUpdate, *, session_id: str, version: int) -> "IntentState":
        """从工具提交的完整快照构造会话状态，会话归属与版本由服务侧给定。"""
        return cls.model_validate({**update.model_dump(), "session_id": session_id, "version": version})


class IntentStateView(IntentState):
    """意图状态的传输视图：待确认时携带触发留档的锚点字段。"""

    confirmation_id: Optional[str] = Field(default=None, exclude_if=lambda v: v is None)
    message_id: Optional[str] = Field(default=None, exclude_if=lambda v: v is None)

    @classmethod
    def from_state(cls, state: IntentState, confirmation: Optional["IntentConfirmation"] = None) -> "IntentStateView":
        """从会话状态构造传输视图，传入留档则携带其锚点。"""
        fields = state.model_dump()
        if confirmation is not None:
            fields.update(confirmation_id=confirmation.confirmation_id, message_id=confirmation.message_id)
        return cls.model_validate(fields)


ConfirmationStatus = Literal["open", "answered"]


class IntentConfirmationAnswer(BaseModel):
    """用户对一次意图确认的回应：确认进入创作或要求继续调整。"""

    model_config = ConfigDict(extra="forbid")

    signal: str
    label: str


class IntentConfirmation(IntentSnapshot):
    """意图确认留档：待确认时固化的意图快照加持久化身份与作答状态。"""

    confirmation_id: str
    session_id: str
    # 触发意图状态更新的助手消息，前端据此将卡原位挂回对话。
    message_id: Optional[str] = None
    status: ConfirmationStatus = "open"
    answer: Optional[IntentConfirmationAnswer] = None
    created_at: float = Field(default_factory=time.time)

    @classmethod
    def from_snapshot(
        cls, snapshot: IntentSnapshot, *, confirmation_id: str, session_id: str,
        message_id: Optional[str] = None,
    ) -> "IntentConfirmation":
        """固化一份意图快照为待确认留档。"""
        fields = snapshot.model_dump(include=set(IntentSnapshot.model_fields))
        fields.update(confirmation_id=confirmation_id, session_id=session_id, message_id=message_id)
        return cls.model_validate(fields)

    def snapshot_fields(self) -> dict:
        """落库快照列的内容：意图快照加已作答时的作答记录。"""
        fields = self.model_dump(include=set(IntentSnapshot.model_fields), mode="json")
        if self.answer:
            fields["answer"] = self.answer.model_dump(mode="json", exclude_none=True)
        return fields


class IntentConfirmationView(IntentSnapshot):
    """意图确认留档的传输视图：不带会话归属，空锚点与空作答不出场。"""

    confirmation_id: str
    message_id: Optional[str] = Field(default=None, exclude_if=lambda v: v is None)
    status: ConfirmationStatus = "open"
    answer: Optional[IntentConfirmationAnswer] = Field(default=None, exclude_if=lambda v: v is None)
    created_at: float = Field(default_factory=time.time)

    @classmethod
    def from_confirmation(cls, confirmation: IntentConfirmation) -> "IntentConfirmationView":
        """从留档构造传输视图。"""
        fields = confirmation.model_dump(include=set(IntentSnapshot.model_fields))
        fields.update(
            confirmation_id=confirmation.confirmation_id,
            message_id=confirmation.message_id,
            status=confirmation.status,
            answer=confirmation.answer,
            created_at=confirmation.created_at,
        )
        return cls.model_validate(fields)


def render_intent_state(state: IntentState) -> str:
    """序列化意图快照正文，最终标签由提示词装配侧添加。"""
    payload = state.model_dump(mode="json", exclude={"session_id", "version", "updated_at"})
    return json.dumps(payload, ensure_ascii=False, indent=2)
