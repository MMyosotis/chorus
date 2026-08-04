"""消息模型：按角色区分用户、助手、工具三类，及消息序列构造的纯操作。

系统提示不入库，每次现拼；消息不可变，改历史只能新增行。
"""

from __future__ import annotations

import json
from typing import Annotated, Iterable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.trace import MessageTrace, ThinkingSegment, ToolInvocation


class _MessageBase(BaseModel):
    """所有 role 消息的公共字段。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    session_id: str
    created_at: float


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str

    def to_provider_dict(self) -> dict:
        return {"role": "user", "content": self.content}


class ToolCallSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    arguments_json: str

    def to_provider_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments_json},
        }

    @classmethod
    def from_arguments(cls, id: str, name: str, arguments: dict) -> ToolCallSpec:
        return cls(id=id, name=name, arguments_json=json.dumps(arguments, ensure_ascii=False))


class AssistantMessage(_MessageBase):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: list[ToolCallSpec] = Field(default_factory=list)

    def to_provider_dict(self) -> dict:
        entry: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            entry["tool_calls"] = [call.to_provider_dict() for call in self.tool_calls]
        return entry


class ToolMessage(_MessageBase):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    content: str

    def to_provider_dict(self) -> dict:
        return {"role": "tool", "tool_call_id": self.tool_call_id, "content": self.content}


Message = Annotated[
    Union[UserMessage, AssistantMessage, ToolMessage],
    Field(discriminator="role"),
]


class MessageView(BaseModel):
    """前端视图：滤掉工具噪音，挂回助手的思考与工具元数据。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)


def build_provider_messages(system_prompt: str, messages: Iterable[Message]) -> list[dict]:
    """构建发给模型的消息序列：系统提示在前，历史消息按序透传。"""
    result: list[dict] = [{"role": "system", "content": system_prompt}]
    result.extend(message.to_provider_dict() for message in messages)
    return result


def build_history_view(
    messages: Iterable[Message],
    traces: dict[str, MessageTrace],
) -> list[MessageView]:
    """前端视图：滤掉工具消息，助手消息挂回思考与工具摘要。

    轨迹由调用方预取注入，避免逐条查询。缺失轨迹退化为空。
    """
    result: list[MessageView] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            result.append(MessageView(id=msg.id, role="user", content=msg.content))
        elif isinstance(msg, AssistantMessage):
            trace = traces.get(msg.id)
            result.append(MessageView(
                id=msg.id,
                role="assistant",
                content=msg.content or "",
                thinking=trace.thinking if trace else [],
                tools=trace.tools if trace else [],
            ))
    return result
