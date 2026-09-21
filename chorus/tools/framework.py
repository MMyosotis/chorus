"""工具框架：工具基类、运行时上下文与调度器。

调度器按白名单筛 schema、统一执行计时包错，联网搜索开关内部查设置服务。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Iterable, Literal, Optional

from chorus.domain.log import get_logger
from chorus.services.settings import SettingsService
from chorus.tools.models import ToolCall, ToolSchema

_logger = get_logger("tool")

_DISPLAY_MAX_LEN = 200

WEB_SEARCH_TOOL_NAME = "baidu_search"


@dataclass(frozen=True)
class ToolOutcome:
    """工具执行后的走向信号，循环据类型分流不按工具名。"""
    content: str


def format_tool_result(content: str) -> str:
    """把正常工具正文包成工具结果块。"""
    return f"<tool_result>\n{content}\n</tool_result>"


def format_error(content: str) -> str:
    """把错误正文包成错误块。"""
    return f"<error>\n{content}\n</error>"


@dataclass(frozen=True)
class Reply(ToolOutcome):
    """回传型：内容作为工具结果回传模型，循环继续。"""


@dataclass(frozen=True)
class Suspend(ToolOutcome):
    """挂起型：循环关流等外部信号 resume 续跑，不回传模型。内容如实记录结果，落库与回传同路径。"""


@dataclass(frozen=True)
class ToolRunResult:
    """工具运行的统一返回：构造时包裹模型可见正文。"""
    outcome: ToolOutcome
    units_produced: int = 0
    events: tuple = ()
    is_error: bool = False

    def __post_init__(self):
        formatter = format_error if self.is_error else format_tool_result
        object.__setattr__(self, "outcome", replace(self.outcome, content=formatter(self.outcome.content)))


@dataclass(frozen=True)
class DispatchResult:
    """派发返回：走向、耗时与结构化产物。"""
    outcome: ToolOutcome
    duration_ms: int
    units_produced: int = 0
    events: tuple = ()
    status: Literal["success", "error"] = "success"


@dataclass
class ToolContext:
    """传给工具运行的运行时上下文。"""

    session_id: Optional[str] = None
    message_id: Optional[str] = None


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict
    running_label: Optional[str] = None
    activity_kind: str = ""
    activity_detail_arg: str = ""

    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)

    def display(self, arguments: dict) -> str:
        return self.name

    @abstractmethod
    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult: ...

    def resolve_external(self, session_id: str, signal: str, payload: Optional[dict] = None) -> str:
        """工具挂起后被外部信号解开时的语义：翻状态、返灌回工具结果的文案。默认未实现。"""
        raise NotImplementedError(f"{self.name} 不支持外部信号解开")


class ToolDispatch:
    def __init__(self, tools: list[Tool], settings_service: SettingsService):
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}
        self._settings = settings_service

    def get_tool(self, name: str) -> Optional[Tool]:
        """按名字取工具实例，供编排层调用挂起型工具的外部解开语义。"""
        return self._tools.get(name)

    def select_schemas(self, names: Iterable[str]) -> list[dict]:
        """按名字白名单筛工具 schema，联网搜索关闭时剔除搜索工具。未注册名字静默跳过。"""
        web_search_on = self._settings.get_web_search()
        return [
            tool.schema().format()
            for tool in self._tools.values()
            if tool.name in names
            and (web_search_on or tool.name != WEB_SEARCH_TOOL_NAME)
        ]

    def format_display(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"(未知工具: {name})"
        text = tool.display(arguments)
        text = text.replace("\n", " ").replace("\r", " ").strip()
        if len(text) > _DISPLAY_MAX_LEN:
            return text[:_DISPLAY_MAX_LEN] + "…"
        return text

    def running_label(self, name: str) -> str:
        tool = self._tools.get(name)
        return (tool and tool.running_label) or "工具调用中"

    def activity(self, name: str, arguments: dict) -> tuple[str, str]:
        """工具运行时的活动态:类型与明细(从声明参数取)。未声明则空。"""
        tool = self._tools.get(name)
        if tool is None or not tool.activity_kind:
            return "", ""
        detail = ""
        if tool.activity_detail_arg:
            detail = str(arguments.get(tool.activity_detail_arg) or "")
        return tool.activity_kind, detail

    def dispatch(self, call: ToolCall, ctx: ToolContext) -> DispatchResult:
        """统一执行入口：找工具、计时包错、归一返回。意外异常兜底转回传。"""
        tool = self._tools.get(call.name)
        if tool is None:
            return DispatchResult(
                outcome=ToolRunResult(Reply(f"Error: unknown tool '{call.name}'"), is_error=True).outcome,
                duration_ms=0, status="error",
            )

        start = perf_counter()
        try:
            raw = tool.run(call.arguments, ctx)
        except Exception as e:
            _logger.exception("tool execution failed", extra={"tool": call.name})
            return DispatchResult(
                outcome=ToolRunResult(Reply(f"Error executing tool '{call.name}': {e}"), is_error=True).outcome,
                duration_ms=int((perf_counter() - start) * 1000),
                status="error",
            )
        return DispatchResult(
            outcome=raw.outcome,
            duration_ms=int((perf_counter() - start) * 1000),
            units_produced=raw.units_produced,
            events=raw.events,
        )
