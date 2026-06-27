"""工具框架：Tool ABC + 运行时上下文 + 调度器（含白名单筛选）。

零件：Tool（抽象基类）、ToolContext（运行时上下文）、ToolDispatch（查找 / 执行 /
筛选入口——select_schemas 按名字白名单筛 schema，全集取自调度器自身、web_search 开关
内部查 SettingsService，都不外部注入；dispatch 统一计时包错）。工具登记装配见
tools/registry.py 的 build_tool_dispatch。
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
    """tool 执行后的走向信号。loop 据 outcome 类型分流，不按工具名。"""


@dataclass(frozen=True)
class Reply(ToolOutcome):
    """回传型：content 作为 tool_result 回传模型，loop 继续。"""
    content: str


@dataclass(frozen=True)
class Terminal(ToolOutcome):
    """终止型：loop 不回传模型，交编排层据此结束本轮。

    content 如实记录工具执行结果（落库 + trace 共用），由 Tool 提供——与 Reply 同形，
    不写死默认值。外界只用 isinstance(..., Terminal) 判终止，tool_result 走与 Reply 相同
    的落库路径，不做特殊处理。
    """
    content: str


@dataclass(frozen=True)
class DispatchResult:
    """dispatch 返回：outcome（含 content，走向 + 落库文本）+ duration_ms（dispatch 计时）。

    content 不在此重复存——外界从 outcome.content 取；duration_ms 是 dispatch 新增信息，
    outcome 上没有，故存此。
    """
    outcome: ToolOutcome
    duration_ms: int


@dataclass
class ToolContext:
    """传给 Tool.run 的运行时上下文。"""

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
    def run(self, arguments: dict, ctx: ToolContext) -> ToolOutcome: ...


class ToolDispatch:
    def __init__(self, tools: list[Tool], settings_service: SettingsService):
        self._tools: dict[str, Tool] = {t.name: t for t in tools}
        self._settings = settings_service

    def select_schemas(self, names: Iterable[str]) -> list[dict]:
        """按名字白名单筛本调度器的工具 schema：取交集；web_search 关闭时再剔除 baidu_search。

        全集取自调度器自身（self._tools），web_search 开关内部查 SettingsService，
        都不外部注入；只对命中的工具生成 OpenAI schema。
        names 中未注册的名字静默跳过。结果按工具注册顺序。
        """
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
        """统一执行入口：找工具、try/except 包错、计时，返回 DispatchResult。

        - 正常：outcome = tool.run(...)（Reply 或 Terminal，content 即落库文本）。
        - 意外异常：强制 Reply(错误文本)，框架 fail-open 兜底，不掺业务走向。
        duration_ms 是 dispatch 计时；content 在 outcome 上，不另存。
        ctx 由调用方造（ToolContext(session_id=...)），不经工厂封装。
        """
        tool = self._tools.get(call.name)
        if tool is None:
            return DispatchResult(
                outcome=Reply(f"Error: unknown tool '{call.name}'"),
                duration_ms=0,
            )

        start = perf_counter()
        try:
            outcome = tool.run(call.arguments, ctx)
        except Exception as e:
            return DispatchResult(
                outcome=Reply(f"Error executing tool '{call.name}': {e}"),
                duration_ms=int((perf_counter() - start) * 1000),
            )
        return DispatchResult(
            outcome=outcome,
            duration_ms=int((perf_counter() - start) * 1000),
        )
