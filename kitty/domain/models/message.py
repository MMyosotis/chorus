"""消息模型：sealed 联合（按 role 区分 user / assistant / tool）。

设计要点：
- 历史 session dict 里的 `_meta_message_id` 升级为正式 `id` 字段；user / tool 的 id 也由后端生成。
- 不同 role 的合法字段不同，用 discriminator='role' 的联合精确建模。
- System message 不存库（每次由 domain.services.prompt.build_system_prompt 现拼），故不在联合内。
- frozen + extra=forbid：消息不可变，"改历史"只能 append 新行。
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from kitty.domain.models.trace import ThinkingSegment, ToolInvocation


class _MessageBase(BaseModel):
    """所有 role 消息的公共字段。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    session_id: str
    seq: int  # 在 session 内的递增序号，落库主键的一部分
    created_at: float


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
        entry: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                }
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
    """前端 GET /messages 用的视图：过滤 system / tool 噪音，
    把该 assistant message 的 thinking + tools 元数据从 trace 聚合挂回。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: list[ThinkingSegment] = Field(default_factory=list)
    tools: list[ToolInvocation] = Field(default_factory=list)
