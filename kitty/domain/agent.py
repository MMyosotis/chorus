"""AgentContext：贯穿一次对话回合的迭代期可变状态。

设计要点（plan M3）：
- 用 @dataclass 而非 Pydantic：高频 mutation、无需校验/序列化。
- **不持 session dict / store 引用** —— hook 经构造器注入的 SessionService 访问数据，
  数据流向变为单向 hook → service → repo → db。
- 按生命周期细分：回合级固定输入留在顶层；同生同灭的单轮状态收进 TurnState，
  异常回滚账本收进 RollbackLedger，退出结果收进 LoopOutcome。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from kitty.domain.trace import ThinkingSegment


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


@dataclass
class RollbackLedger:
    """本回合新增 assistant message id 账本，异常回滚时用于删对应 trace。"""

    new_message_ids: list[str] = field(default_factory=list)

    def record(self, message_id: str) -> None:
        self.new_message_ids.append(message_id)


@dataclass
class LoopOutcome:
    """回合退出状态。"""

    exception: Optional[BaseException] = None
    done_reason: Optional[str] = None


@dataclass
class AgentContext:
    # 回合级固定输入（整回合不变）
    session_id: str
    user_message: str
    tool_schemas: list[dict]
    history_snapshot_len: int  # 入口前该会话的 message 数量，回滚锚点
    image_model: Optional[str] = None  # 用户选定的生图模型逻辑名，注入 ToolContext
    chat_model: Optional[str] = None  # 本回合实际调用的真实 model 名（trace 用）

    turn: TurnState = field(default_factory=TurnState)
    rollback: RollbackLedger = field(default_factory=RollbackLedger)
    outcome: LoopOutcome = field(default_factory=LoopOutcome)
