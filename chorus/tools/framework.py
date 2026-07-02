"""工具框架：工具基类、运行时上下文与调度器。

调度器负责按白名单筛 schema、统一执行计时包错。联网搜索开关内部查设置服务，不外部注入。
工具登记装配见登记模块。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, Optional

from chorus.services.settings import SettingsService
from chorus.tools.models import ToolCall, ToolSchema

_DISPLAY_MAX_LEN = 200

# 联网搜索能力对应的工具名（baidu_search 工具的 name）
WEB_SEARCH_TOOL_NAME = "baidu_search"


class ToolOutcome:
    """工具执行后的走向信号，循环据类型分流不按工具名。"""


@dataclass(frozen=True)
class Reply(ToolOutcome):
    """回传型：内容作为工具结果回传模型，循环继续。"""
    content: str


@dataclass(frozen=True)
class Terminal(ToolOutcome):
    """终止型：循环不回传模型，交编排层结束本轮。内容如实记录结果，落库与回传同路径。"""
    content: str


@dataclass(frozen=True)
class ToolRunResult:
    """工具运行的双通道返回：走向（模型可见）与结构化产物（活动翻译层用）。

    工具可返回裸走向，视作产物为空。
    """
    outcome: ToolOutcome
    activity_meta: Optional[dict] = None


@dataclass(frozen=True)
class DispatchResult:
    """派发返回：走向、耗时与结构化产物。"""
    outcome: ToolOutcome
    duration_ms: int
    activity_meta: Optional[dict] = None


@dataclass
class ToolContext:
    """传给工具运行的运行时上下文。"""

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
    def run(self, arguments: dict, ctx: ToolContext) -> "ToolOutcome | ToolRunResult": ...


class ToolDispatch:
    def __init__(self, tools: list[Tool], settings_service: SettingsService):
        self._tools: dict[str, Tool] = {t.name: t for t in tools}
        self._settings = settings_service

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

    def dispatch(self, call: ToolCall, ctx: ToolContext) -> DispatchResult:
        """统一执行入口：找工具、计时包错、归一返回。意外异常兜底转回传。"""
        tool = self._tools.get(call.name)
        if tool is None:
            return DispatchResult(
                outcome=Reply(f"Error: unknown tool '{call.name}'"),
                duration_ms=0, activity_meta=None,
            )

        start = perf_counter()
        try:
            raw = tool.run(call.arguments, ctx)
        except Exception as e:
            return DispatchResult(
                outcome=Reply(f"Error executing tool '{call.name}': {e}"),
                duration_ms=int((perf_counter() - start) * 1000),
                activity_meta=None,
            )
        if isinstance(raw, ToolRunResult):
            return DispatchResult(
                outcome=raw.outcome,
                duration_ms=int((perf_counter() - start) * 1000),
                activity_meta=raw.activity_meta,
            )
        return DispatchResult(
            outcome=raw,
            duration_ms=int((perf_counter() - start) * 1000),
            activity_meta=None,
        )
