"""会话级意图状态：主 Agent 每轮维护的结构化工作记忆。"""

from __future__ import annotations

import time
from typing import Any, Literal

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
    image_count: int = Field(3, description="配图数量，默认 3")
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
