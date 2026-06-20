"""工具领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ToolSchema(BaseModel):
    """OpenAI function 描述。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    parameters: dict

    def to_openai(self) -> dict:
        return {"type": "function", "function": self.model_dump()}


class ToolCall(BaseModel):
    """规范化后的工具调用（arguments 已 json.loads）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    arguments: dict


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_call_id: str
    name: str
    content: str
    duration_ms: int
    display: str
    is_error: bool = False
