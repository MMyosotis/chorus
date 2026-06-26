# kitty/agents/runtime.py
"""agent loop 运行时脚手架：AgentContext / TurnState / LoopOutcome。

从 domain/agent.py 迁入——它们是 loop 的可变运行时状态，非业务概念（domain 无 Agent
表/无 Agent 业务规则），留 domain 踩「防 domain 杂项化滑坡」红线。与 supervisor/subagent
同包共享。多智能体扩展字段：task_id（subagent 用）、source（hook 区分来源）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from chorus.domain.trace import ThinkingSegment

if TYPE_CHECKING:
    from chorus.domain.stream import StreamResult


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
        self.iteration_index = index
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
    # 回合级固定输入（整回合不变）
    session_id: str
    user_message: str = ""
    tool_schemas: list[dict] = field(default_factory=list)
    chat_model: Optional[str] = None
    # 多智能体扩展（hook 据此区分来源 + trace 关联）
    source: str = "supervisor"        # 'supervisor' | 'subagent'
    task_id: Optional[str] = None     # subagent 填；supervisor 空

    turn: TurnState = field(default_factory=TurnState)
    outcome: LoopOutcome = field(default_factory=LoopOutcome)
