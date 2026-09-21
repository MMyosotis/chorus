"""会话级选项征询：一个工具调用可向用户提出一组选择题。"""

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


class OptionQuestion(BaseModel):
    """问题组中的一个选择题；答案按问题数组顺序回填。"""

    model_config = ConfigDict(extra="forbid")

    question: str
    options: list[OptionItem]
    allow_custom: bool = True


class OptionPromptDef(BaseModel):
    """提问定义：多个选择题整体作为一次挂起写入。"""

    model_config = ConfigDict(extra="forbid")

    questions: list[OptionQuestion]


class OptionAnswer(BaseModel):
    """用户对问题组中一道题的确认结果。"""

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
    answers: list[OptionAnswer] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    def prompt_fields(self) -> dict:
        """落库提问列的内容：提问定义加已作答时的作答记录。"""
        fields = self.model_dump(include=set(OptionPromptDef.model_fields), mode="json")
        if self.answers:
            fields["answers"] = [answer.model_dump(mode="json", exclude_none=True) for answer in self.answers]
        return fields


class OptionAnswerView(OptionAnswer):
    """作答的传输视图：未填的补充说明不出场。"""

    custom_text: Optional[str] = Field(default=None, exclude_if=lambda v: v is None)


class OptionPromptView(OptionPromptDef):
    """选项征询单的传输视图：不带会话归属，空锚点不出场。"""

    prompt_id: str
    message_id: Optional[str] = Field(default=None, exclude_if=lambda v: v is None)
    status: OptionStatus = "open"
    answers: list[OptionAnswerView] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    @classmethod
    def from_prompt(cls, prompt: OptionPrompt) -> "OptionPromptView":
        """从征询单构造传输视图。"""
        return cls.model_validate({
            **prompt.model_dump(include=set(OptionPromptDef.model_fields)),
            "prompt_id": prompt.prompt_id,
            "message_id": prompt.message_id,
            "status": prompt.status,
            "answers": [OptionAnswerView.model_validate(answer.model_dump()) for answer in prompt.answers],
            "created_at": prompt.created_at,
        })
