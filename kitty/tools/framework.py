"""工具框架：schema 选择规则 + Tool ABC + 运行时上下文 + 注册表。

零件：select_tool_schemas（按联网搜索开关过滤）、Tool（抽象基类）、
ToolContext（运行时上下文）、ToolRegistry（查找 / 执行入口，dispatch 统一计时包错）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Iterable, Optional

from kitty.domain.skill import SkillLoader
from kitty.tools.models import ToolCall, ToolResult, ToolSchema

_DISPLAY_MAX_LEN = 200

# 联网搜索能力对应的工具名（baidu_search 工具的 name）
WEB_SEARCH_TOOL_NAME = "baidu_search"


def select_tool_schemas(schemas: list[dict], *, web_search: bool) -> list[dict]:
    """按联网搜索开关过滤 OpenAI 工具 schema：关闭时移除 baidu_search。"""
    if web_search:
        return schemas
    return [
        s for s in schemas
        if s.get("function", {}).get("name") != WEB_SEARCH_TOOL_NAME
    ]


def select_schemas_by_names(all_schemas: list[dict], names: Iterable[str]) -> list[dict]:
    """按工具名白名单筛 OpenAI 工具 schema（subagent 按 agent_type 工具白名单筛）。

    保留 names 顺序对应的 schema；names 中不存在于 all_schemas 的名字静默跳过。
    """
    wanted = set(names)
    return [
        s for s in all_schemas
        if s.get("function", {}).get("name") in wanted
    ]


@dataclass
class ToolContext:
    """传给 Tool.run 的运行时上下文。"""

    skill_loader: SkillLoader
    session_id: Optional[str] = None
    image_model: Optional[str] = None  # 用户选定的生图模型逻辑名（generate_image 用）


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}
    running_label: Optional[str] = None

    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)

    def display(self, arguments: dict) -> str:
        return self.name

    @abstractmethod
    def run(self, arguments: dict, ctx: ToolContext) -> str:
        ...


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._by_name: dict[str, Tool] = {t.name: t for t in tools}

    def get(self, name: str) -> Optional[Tool]:
        return self._by_name.get(name)

    def schemas_openai(self) -> list[dict]:
        return [t.schema().to_openai() for t in self._by_name.values()]

    def format_display(self, name: str, arguments: dict) -> str:
        tool = self._by_name.get(name)
        if tool is None:
            return name or "tool"
        try:
            text = tool.display(arguments or {})
        except Exception:
            return name
        if not isinstance(text, str) or not text.strip():
            return name
        text = text.replace("\n", " ").replace("\r", " ").strip()
        if len(text) > _DISPLAY_MAX_LEN:
            text = text[:_DISPLAY_MAX_LEN] + "…"
        return text

    def running_label(self, name: str) -> Optional[str]:
        tool = self._by_name.get(name)
        return tool.running_label if tool else None

    def dispatch(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """统一执行入口：找工具、try/except 包错、计时、返回 ToolResult。"""
        display = self.format_display(call.name, call.arguments)
        tool = self._by_name.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id, name=call.name,
                content=f"Error: unknown tool '{call.name}'",
                duration_ms=0, display=display, is_error=True,
            )
        t0 = perf_counter()
        try:
            content = tool.run(call.arguments, ctx)
            is_error = False
        except Exception as e:
            content = f"Error executing tool '{call.name}': {e}"
            is_error = True
        duration_ms = int((perf_counter() - t0) * 1000)
        return ToolResult(
            tool_call_id=call.id, name=call.name, content=content,
            duration_ms=duration_ms, display=display, is_error=is_error,
        )


ToolCtxFactory = Callable[[Optional[str], Optional[str]], ToolContext]
