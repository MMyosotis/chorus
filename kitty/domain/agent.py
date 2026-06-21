"""AgentContext：贯穿一次对话回合的迭代期可变状态。

用 @dataclass 而非 Pydantic：高频 mutation、无需校验/序列化。按生命周期细分：
回合级固定输入留顶层；单轮状态收进 TurnState，退出结果收进 LoopOutcome。
hook 经注入的 SessionService 访问数据，不持 session/store 引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from kitty.domain.trace import ThinkingSegment

if TYPE_CHECKING:
    from kitty.domain.stream import StreamResult


@dataclass
class TurnState:
    """单轮迭代可变累积状态，每轮开始 reset。"""

    iteration_index: int = 0
    message_id: str = ""
    text_parts: list[str] = field(default_factory=list)
    accumulated_tool_calls: dict[int, dict] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)
    provider_messages: Optional[list[dict]] = None

    def reset(self, index: int) -> None:
        """下一轮开始前清空本轮累积，重置索引与 message_id。"""
        self.iteration_index = index
        self.message_id = ""
        self.text_parts.clear()
        self.accumulated_tool_calls.clear()
        self.finish_reason = None
        self.thinking_segments.clear()
        self.provider_messages = None

    def apply_stream(self, result: "StreamResult") -> None:
        """把 consume_stream 的累积结果写入回合状态（集中字段写入，避免散落 unpack）。"""
        self.text_parts = result.text_parts
        self.accumulated_tool_calls = result.tool_calls
        self.finish_reason = result.finish_reason
        self.thinking_segments = result.thinking_segments


@dataclass
class LoopOutcome:
    """回合退出状态。"""

    exception: Optional[BaseException] = None


@dataclass
class AgentContext:
    # 回合级固定输入（整回合不变）
    session_id: str
    user_message: str
    tool_schemas: list[dict]
    image_model: Optional[str] = None  # 用户选定的生图模型逻辑名，注入 ToolContext
    chat_model: Optional[str] = None  # 本回合实际调用的真实 model 名（trace 用）

    turn: TurnState = field(default_factory=TurnState)
    outcome: LoopOutcome = field(default_factory=LoopOutcome)
