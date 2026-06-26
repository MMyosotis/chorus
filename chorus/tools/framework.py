"""工具框架：schema 选择规则 + Tool ABC + 运行时上下文 + 注册表。

零件：select_tool_schemas（按联网搜索开关过滤）、Tool（抽象基类）、
ToolContext（运行时上下文）、ToolRegistry（查找 / 执行入口，dispatch 统一计时包错）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterable, Optional

from chorus.domain.skill import SkillLoader
from chorus.tools.models import ToolCall, ToolResult, ToolSchema

_DISPLAY_MAX_LEN = 200

# 联网搜索能力对应的工具名（baidu_search 工具的 name）
WEB_SEARCH_TOOL_NAME = "baidu_search"


class ToolOutcome:
    """tool 执行后的走向信号。loop 据 outcome 类型分流，不按工具名。"""


@dataclass(frozen=True)
class Reply(ToolOutcome):
    """回传型：content 作为 tool_result 回传模型，loop 继续。"""
    content: str


@dataclass(frozen=True)
class Terminal(ToolOutcome):
    """分流型：携带载荷，loop 不回传模型，交编排层按载荷执行重副作用后结束本轮。

    summary 是 tool_result.content 的语义摘要（落库 + trace 共用），由 Tool 提供；
    不给则 dispatch 用通用占位。
    """
    payload: Any
    summary: str = "已执行"


@dataclass(frozen=True)
class DispatchResult:
    """dispatch 返回：tool_result（落库+trace 共用 content）+ outcome（走向）。"""
    tool_result: ToolResult
    outcome: ToolOutcome


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
    def run(self, arguments: dict, ctx: ToolContext) -> ToolOutcome:
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

    def dispatch(self, call: ToolCall, ctx: ToolContext) -> DispatchResult:
        """统一执行入口：找工具、try/except 包错、计时，返回 DispatchResult。

        - Reply：tool_result.content = Reply.content（落库 + trace 单一来源）。
        - Terminal：tool_result.content = outcome.summary（Tool 自定义摘要，不给则通用占位）。
        - 意外异常：强制 Reply(错误文本) + is_error=True，框架 fail-open 兜底，不掺业务走向。
        """
        display = self.format_display(call.name, call.arguments)
        tool = self._by_name.get(call.name)
        if tool is None:
            tr = ToolResult(
                tool_call_id=call.id, name=call.name,
                content=f"Error: unknown tool '{call.name}'",
                duration_ms=0, display=display, is_error=True,
            )
            return DispatchResult(tool_result=tr, outcome=Reply(tr.content))
        t0 = perf_counter()
        try:
            outcome = tool.run(call.arguments, ctx)
        except Exception as e:  # noqa: BLE001 — 框架兜底意外异常
            content = f"Error executing tool '{call.name}': {e}"
            tr = ToolResult(
                tool_call_id=call.id, name=call.name, content=content,
                duration_ms=int((perf_counter() - t0) * 1000),
                display=display, is_error=True,
            )
            return DispatchResult(tool_result=tr, outcome=Reply(content))
        duration_ms = int((perf_counter() - t0) * 1000)
        if isinstance(outcome, Terminal):
            tr = ToolResult(
                tool_call_id=call.id, name=call.name, content=outcome.summary,
                duration_ms=duration_ms, display=display, is_error=False,
            )
            return DispatchResult(tool_result=tr, outcome=outcome)
        # Reply
        tr = ToolResult(
            tool_call_id=call.id, name=call.name, content=outcome.content,
            duration_ms=duration_ms, display=display, is_error=False,
        )
        return DispatchResult(tool_result=tr, outcome=outcome)


ToolCtxFactory = Callable[[Optional[str]], ToolContext]
