"""消息模型：按角色区分用户、助手、工具三类，及消息序列构造的纯操作。

系统提示不入库，每次现拼；消息不可变，改历史只能新增行。
"""

from __future__ import annotations

import json
import uuid6
from typing import Annotated, Iterable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from chorus.domain.stream import StreamResult, ToolCallAccumulator
from chorus.domain.trace import MessageTrace, ThinkingSegment, ToolInvocation


class _MessageBase(BaseModel):
    """所有 role 消息的公共字段。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    session_id: str
    created_at: float

    def payload_chars(self) -> int:
        """占用的正文字符量，供上下文压缩估算。"""
        return len(self.content or "")

    @classmethod
    def transient(cls, session_id: str, **fields) -> Self:
        """构造不落库的内存历史消息，身份字段自动生成。"""
        return cls(id=str(uuid6.uuid7()), session_id=session_id, created_at=0.0, **fields)


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str

    def to_provider_dict(self) -> dict:
        return {"role": "user", "content": self.content}

    def to_view(self, trace: Optional[MessageTrace]) -> Optional[MessageView]:
        return MessageView(id=self.id, role="user", content=self.content)

    def to_history_line(self) -> str:
        return f"用户：{self.content}"


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

    @classmethod
    def from_accumulator(cls, acc: ToolCallAccumulator) -> ToolCallSpec:
        return cls(id=acc.id, name=acc.name, arguments_json=acc.arguments)


class AssistantMessage(_MessageBase):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    reasoning: Optional[str] = None
    tool_calls: list[ToolCallSpec] = Field(default_factory=list)

    def to_provider_dict(self) -> dict:
        entry: dict = {"role": "assistant", "content": self.content}
        if self.reasoning:
            entry["reasoning_content"] = self.reasoning
        if self.tool_calls:
            entry["tool_calls"] = [call.to_provider_dict() for call in self.tool_calls]
        return entry

    def to_view(self, trace: Optional[MessageTrace]) -> Optional[MessageView]:
        return MessageView(
            id=self.id, role="assistant", content=self.content or "",
            thinking=trace.thinking if trace else [],
            tools=trace.tools if trace else [],
        )

    def to_history_line(self) -> str:
        text = self.content or ""
        if self.tool_calls:
            names = "、".join(call.name for call in self.tool_calls)
            text = f"{text}（调用工具：{names}）" if text else f"（调用工具：{names}）"
        return f"助手：{text}"

    def payload_chars(self) -> int:
        """正文加思考加各工具调用参数的字符量。"""
        return (
            len(self.content or "")
            + len(self.reasoning or "")
            + sum(len(call.arguments_json) for call in self.tool_calls)
        )

    @classmethod
    def _tool_calls_from_result(cls, result: StreamResult) -> list[ToolCallSpec]:
        return [ToolCallSpec.from_accumulator(acc) for _, acc in sorted(result.tool_calls.items())]

    @classmethod
    def transient_from_stream(cls, session_id: str, result: StreamResult) -> Self:
        """内存草稿整体造，身份字段随手生成。"""
        return cls.transient(
            session_id,
            content=result.text,
            reasoning=result.reasoning,
            tool_calls=cls._tool_calls_from_result(result),
        )

    @classmethod
    def from_stream(
        cls, session_id: str, result: StreamResult, *,
        message_id: str, tool_calls: Optional[list[ToolCallSpec]] = None,
    ) -> Self:
        """落库消息：标识沿用轮首契约，工具清单缺省取流结果、可传实际派发清单覆盖。"""
        return cls(
            id=message_id, session_id=session_id, created_at=0.0,
            content=result.text, reasoning=result.reasoning,
            tool_calls=tool_calls if tool_calls is not None else cls._tool_calls_from_result(result),
        )


class ToolMessage(_MessageBase):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    content: str

    def to_provider_dict(self) -> dict:
        return {"role": "tool", "tool_call_id": self.tool_call_id, "content": self.content}

    def to_view(self, trace: Optional[MessageTrace]) -> Optional[MessageView]:
        return None

    def to_history_line(self) -> str:
        return f"工具[{self.name}]：{self.content}"


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


def build_history_view(messages: Iterable[Message], traces: dict[str, MessageTrace]) -> list[MessageView]:
    """前端视图：工具消息隐去，助手消息挂回思考与工具元数据。"""
    return [view for msg in messages if (view := msg.to_view(traces.get(msg.id))) is not None]


def recent_history_lines(messages: Iterable[Message], limit: int = 12, line_max: int = 300) -> list[str]:
    """近期对话的可读摘要：滤工具噪音，取尾部若干条，超长行截断，供旁路提示词取材。"""
    picked = [msg for msg in messages if not isinstance(msg, ToolMessage)][-limit:]
    lines = []
    for msg in picked:
        line = msg.to_history_line()
        lines.append(line if len(line) <= line_max else line[:line_max] + "…")
    return lines


def recent_chat_block(messages: Iterable[Message], limit: int = 12, line_max: int = 300) -> str:
    """序列化近期对话为标签块，供旁路提示词携带；空会话给占位说明。"""
    lines = recent_history_lines(messages, limit, line_max)
    body = "\n".join(lines) if lines else "（会话刚开始，还没有对话）"
    return f"<recent_chat>\n{body}\n</recent_chat>"


def first_user_text(messages: Iterable[Message]) -> str:
    """返回首条消息文本，供标题生成取材；会话由用户发起，首条即用户输入。"""
    first = next(iter(messages), None)
    return (first.content or "") if first else ""
