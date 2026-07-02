"""agent loop 运行时脚手架：上下文、单轮状态与退出结果。

可变运行时状态，非业务概念，故不归领域层。多智能体扩展字段标识来源与任务。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from chorus.domain.stream import ToolCallAccumulator
from chorus.domain.trace import ThinkingSegment

if TYPE_CHECKING:
    from chorus.domain.stream import StreamResult


@dataclass
class TurnState:
    """单轮可变累积状态，每轮开始重置。"""

    message_id: str = ""
    text_parts: list[str] = field(default_factory=list)
    accumulated_tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)
    provider_messages: Optional[list[dict]] = None

    def reset(self) -> None:
        self.message_id = ""
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
    user_message: str = ""
    tool_schemas: list[dict] = field(default_factory=list)
    chat_model: Optional[str] = None
    # 多智能体扩展，钩子据此区分来源
    source: str = "supervisor"
    task_id: Optional[str] = None

    turn: TurnState = field(default_factory=TurnState)
    outcome: LoopOutcome = field(default_factory=LoopOutcome)
