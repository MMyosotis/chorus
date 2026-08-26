"""agent loop 运行时脚手架：上下文、单轮状态与退出结果，多智能体字段标识来源与任务。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Optional

from chorus.agents.truncation import TruncationGuard
from chorus.domain.events import SseEvent
from chorus.domain.stream import ToolCallAccumulator
from chorus.domain.trace import ThinkingSegment

if TYPE_CHECKING:
    from chorus.domain.stream import StreamResult


class LoopSignal(Enum):
    CONTINUE = "continue"
    SUSPEND = "suspend"
    FINISH = "finish"


@dataclass
class LoopAction:
    """策略对单轮结局的判定：信号与附带事件。事件只被内核消费一次，推荐返回列表或元组。"""

    signal: LoopSignal
    events: Iterable[SseEvent] = ()


@dataclass
class TurnState:
    """单轮可变累积状态，每轮开始重置。"""

    message_id: str = ""
    text_parts: list[str] = field(default_factory=list)
    accumulated_tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)
    provider_messages: Optional[list[dict]] = None

    def reset(self, message_id: str = "") -> None:
        self.message_id = message_id
        self.text_parts.clear()
        self.accumulated_tool_calls.clear()
        self.finish_reason = None
        self.thinking_segments.clear()
        self.provider_messages = None

    def apply_stream(self, result: "StreamResult") -> None:
        self.text_parts = result.text_parts
        self.accumulated_tool_calls = result.tool_calls
        self.finish_reason = result.finish_reason
        self.thinking_segments = result.thinking_segments


@dataclass
class LoopOutcome:
    exception: Optional[BaseException] = None


@dataclass
class AgentContext:
    # 回合级固定输入
    session_id: str
    chat_model: str
    user_message: str = ""
    tool_schemas: list[dict] = field(default_factory=list)
    # 多智能体扩展，钩子据此区分来源
    source: str = "supervisor"
    task_id: Optional[str] = None

    # 运行级进度，跨轮累加
    step: int = 0
    turn: TurnState = field(default_factory=TurnState)
    truncation: TruncationGuard = field(default_factory=TruncationGuard)
    outcome: LoopOutcome = field(default_factory=LoopOutcome)
