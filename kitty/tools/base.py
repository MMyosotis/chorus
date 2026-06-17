"""Tool 框架：Tool 抽象基类、ToolContext、ToolRegistry。

替代旧模块级 _REGISTRY / @tool 装饰器：工具是类，由 AppContainer 装配进 ToolRegistry，
ToolCallHook 经 registry.dispatch 执行。Registry 是工具的唯一查找 / 执行入口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Optional

from kitty.domain.models.tool import ToolCall, ToolResult, ToolSchema
from kitty.services.skill import SkillService
from kitty.tools.workspace import WorkspacePolicy

_DISPLAY_MAX_LEN = 200


@dataclass
class ToolContext:
    """传给 Tool.run 的运行时上下文。"""

    workspace: WorkspacePolicy
    skill_service: SkillService
    session_id: Optional[str] = None


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


ToolCtxFactory = Callable[[Optional[str]], ToolContext]
