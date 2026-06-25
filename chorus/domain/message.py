"""消息：sealed 联合模型（按 role 区分 user / assistant / tool）+ 消息序列构造纯操作。

System message 不存库（每次由 prompt.build_system_prompt 现拼），故不在联合内；
frozen + extra=forbid 使消息不可变，改历史只能 append 新行。
"""

from __future__ import annotations

from typing import Annotated, Callable, Iterable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.trace import MessageTrace, ThinkingSegment, ToolInvocation


class _MessageBase(BaseModel):
    """所有 role 消息的公共字段。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    session_id: str
    seq: int  # 在 session 内的递增序号，落库主键的一部分
    created_at: float
    subtype: Optional[str] = None  # None 普通 / "progress" 进度气泡


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str

    def to_provider_dict(self) -> dict:
        return {"role": "user", "content": self.content}


class ToolCallSpec(BaseModel):
    """assistant 决定要调用的工具，保留 LLM 流式拼回的原始字符串形态。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str  # OpenAI 给的 tool_call_id
    name: str
    arguments_json: str


class AssistantMessage(_MessageBase):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None  # 纯 tool_calls 时为 None
    tool_calls: list[ToolCallSpec] = Field(default_factory=list)

    def to_provider_dict(self) -> dict:
        content = self.content
        if self.subtype == "progress" and content:
            # 进度气泡压成单行摘要，避免完整话术污染 supervisor 上下文
            first_line = content.strip().split("\n", 1)[0]
            content = first_line[:40] if len(first_line) > 40 else first_line
            content = f"[进度] {content}"
        entry: dict = {"role": "assistant", "content": content}
        if self.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": tc.arguments_json}}
                for tc in self.tool_calls
            ]
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

    不自行排序——按传入顺序透传；调用方须保证 messages 已按 seq 升序（由
    MessageRepository.list_by_session 的 ORDER BY seq 保证）。
    """
    result: list[dict] = [{"role": "system", "content": system_prompt}]
    result.extend(m.to_provider_dict() for m in messages)
    return result


def build_history_view(
    messages: Iterable[Message],
    trace_of: Callable[[str], MessageTrace],
) -> list[MessageView]:
    """前端视图：过滤 tool，assistant 挂回 thinking/tools（由 trace_of 取每条 assistant 的聚合 trace）。"""
    result: list[MessageView] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            result.append(MessageView(id=msg.id, role="user", content=msg.content))
        elif isinstance(msg, AssistantMessage):
            trace = trace_of(msg.id)
            result.append(
                MessageView(
                    id=msg.id,
                    role="assistant",
                    content=msg.content or "",
                    thinking=trace.thinking,
                    tools=trace.tools,
                )
            )
    return result
