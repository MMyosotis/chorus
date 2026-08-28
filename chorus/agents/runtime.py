"""agent loop 运行时脚手架：上下文、单轮状态与退出结果，多智能体字段标识来源与任务。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from typing import TYPE_CHECKING, Iterable, Literal, Optional

from chorus.agents.chat_model import ModelPricing
from chorus.agents.truncation import TruncationGuard
from chorus.domain.events import SseEvent
from chorus.domain.stream import ToolCallAccumulator
from chorus.domain.trace import ModelUsage, ThinkingSegment

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
class ModelCallStats:
    """单次模型调用的观测记录：成败、耗时、用量。"""

    status: Literal["success", "error"] = "success"
    duration_ms: int = 0
    usage: Optional[ModelUsage] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, *, duration_ms: int, usage: Optional[ModelUsage]) -> "ModelCallStats":
        return cls(duration_ms=duration_ms, usage=usage)

    @classmethod
    def failure(cls, *, duration_ms: int, error: BaseException) -> "ModelCallStats":
        return cls(status="error", duration_ms=duration_ms, error=str(error))


@dataclass
class ModelCallRecorder:
    """模型调用计时器：起表后按成败收口出观测记录。"""

    started_at: float = field(default_factory=perf_counter)

    def success(self, usage: Optional[ModelUsage]) -> ModelCallStats:
        return ModelCallStats.success(duration_ms=self._elapsed_ms(), usage=usage)

    def failure(self, error: BaseException) -> ModelCallStats:
        return ModelCallStats.failure(duration_ms=self._elapsed_ms(), error=error)

    def _elapsed_ms(self) -> int:
        return int((perf_counter() - self.started_at) * 1000)


@dataclass
class TurnState:
    """单轮可变累积状态，每轮开始重置。"""

    message_id: str = ""
    text_parts: list[str] = field(default_factory=list)
    accumulated_tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    thinking_segments: list[ThinkingSegment] = field(default_factory=list)
    provider_messages: list[dict] = field(default_factory=list)
    model_call: ModelCallStats = field(default_factory=ModelCallStats)

    def reset(self, message_id: str = "") -> None:
        self.message_id = message_id
        self.text_parts.clear()
        self.accumulated_tool_calls.clear()
        self.finish_reason = None
        self.thinking_segments.clear()
        self.provider_messages = []
        self.model_call = ModelCallStats()

    def apply_stream(self, result: "StreamResult", *, model_call: ModelCallStats) -> None:
        self.text_parts = result.text_parts
        self.accumulated_tool_calls = result.tool_calls
        self.finish_reason = result.finish_reason
        self.thinking_segments = result.thinking_segments
        self.model_call = model_call


@dataclass
class LoopOutcome:
    exception: Optional[BaseException] = None


@dataclass
class AgentContext:
    # 回合级固定输入
    session_id: str
    chat_model: str
    pricing: Optional[ModelPricing] = None
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
