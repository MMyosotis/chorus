"""工具领域：模型 + 框架 + 登记/调度 + 内置工具 + 外部 client，围绕 tool 单一概念内聚。"""

from __future__ import annotations

from chorus.tools.framework import (
    DispatchResult,
    Reply,
    Terminal,
    Tool,
    ToolContext,
    ToolDispatch,
    ToolOutcome,
    WEB_SEARCH_TOOL_NAME,
)
from chorus.tools.models import ToolCall, ToolSchema
from chorus.tools.registry import build_tool_dispatch

__all__ = [
    "ToolSchema",
    "ToolCall",
    "WEB_SEARCH_TOOL_NAME",
    "Tool",
    "ToolContext",
    "ToolOutcome",
    "Reply",
    "Terminal",
    "DispatchResult",
    "ToolDispatch",
    "build_tool_dispatch",
]
