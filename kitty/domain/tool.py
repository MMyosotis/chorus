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


# 联网搜索能力对应的工具名（baidu_search 工具的 name）
WEB_SEARCH_TOOL_NAME = "baidu_search"


def select_tool_schemas(schemas: list[dict], *, web_search: bool) -> list[dict]:
    """按用户联网搜索开关过滤 OpenAI 工具 schema：关闭时移除 baidu_search。

    纯领域逻辑：输入 OpenAI 格式 schema 列表 + 开关，输出过滤后列表，可脱离 DB/HTTP 独立单测。
    """
    if web_search:
        return schemas
    return [
        s for s in schemas
        if s.get("function", {}).get("name") != WEB_SEARCH_TOOL_NAME
    ]
