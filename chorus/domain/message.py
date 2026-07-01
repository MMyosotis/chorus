"""消息：sealed 联合模型（按 role 区分 user / assistant / tool）+ 消息序列构造纯操作。

System message 不存库（每次由 prompt.build_system_prompt 现拼），故不在联合内；
frozen + extra=forbid 使消息不可变，改历史只能 append 新行。
"""

from __future__ import annotations

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
    """前端视图：过滤 system / tool 噪音，挂回 assistant 的 thinking + tools 元数据。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)


def build_provider_messages(system_prompt: str, messages: Iterable[Message]) -> list[dict]:
    """构建发给 LLM 的消息序列：[system] + 历史消息（各角色自行 to_provider_dict）。

    不自行排序——按传入顺序透传；调用方须保证 messages 已按 id 升序（由
    MessageRepository.list_by_session 的 ORDER BY id 保证，id 为 uuid7 趋势递增）。
    """
    result: list[dict] = [{"role": "system", "content": system_prompt}]
    result.extend(m.to_provider_dict() for m in messages)
    return result


def build_history_view(
    messages: Iterable[Message],
    traces: dict[str, MessageTrace],
) -> list[MessageView]:
    """前端视图：过滤 tool，assistant 挂回 thinking/tools（从预取的 traces 字典按 message_id 取）。

    traces 由调用方（service）预取聚合好注入，避免在 domain 内逐条查 trace（N+1）。
    缺失的 message_id 退化为空 thinking/tools。
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
