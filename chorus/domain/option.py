"""会话级选项征询：主 Agent 向用户出的选择题，用户作答后续跑 loop。"""

from __future__ import annotations

import time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

OptionStatus = Literal["open", "answered"]


class OptionItem(BaseModel):
    """单个选项：标题加简短解释，signal 是后端按序号生成的回传标识。"""

    model_config = ConfigDict(extra="forbid")

    signal: str
    label: str
    description: str


class OptionPromptDef(BaseModel):
    """提问定义：创建时一次写入，落 prompt 列 JSON。"""

    model_config = ConfigDict(extra="forbid")

    question: str
    options: list[OptionItem]
    allow_custom: bool = True


class OptionAnswer(BaseModel):
    """用户对一张选项卡的确认结果，随卡片一同留档。"""

    model_config = ConfigDict(extra="forbid")

    signal: str
    label: str
    custom_text: Optional[str] = None


class OptionPrompt(OptionPromptDef):
    """选项征询单：提问定义加持久化身份与状态。"""

    prompt_id: str
    session_id: str
    # 触发选项征询的助手消息，前端据此将卡原位挂回对话。
    message_id: Optional[str] = None
    status: OptionStatus = "open"
    answer: Optional[OptionAnswer] = None
    created_at: float = Field(default_factory=time.time)
