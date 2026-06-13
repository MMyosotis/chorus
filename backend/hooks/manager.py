"""Hook 框架核心：Event 枚举、AgentContext、HookManager。

设计要点：核心 agent loop 只在生命周期节点 trigger 事件，
扩展逻辑通过注册回调订阅。Hook 回调签名：

    (ctx: AgentContext) -> Iterable[dict] | None

返回 dict 的 iterable 会被主 loop yield 出去（即 SSE 事件）。回调 raise 时
manager 捕获并日志告警，默认 fail-open 不中断主流程。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.conversations.store import ConversationStore

logger = logging.getLogger(__name__)


class Event(str, Enum):
    LoopStart = "LoopStart"
    IterationStart = "IterationStart"
    BeforeModelRequest = "BeforeModelRequest"
    AssistantTextResponse = "AssistantTextResponse"
    ToolCallsDetected = "ToolCallsDetected"
    IterationEnd = "IterationEnd"
    LoopEnd = "LoopEnd"
    LoopError = "LoopError"


@dataclass
class AgentContext:
    """贯穿一次 chat_stream 调用的上下文。"""

    conversation_id: str
    user_message: str
    conv: dict
    store: "ConversationStore"
    history_snapshot_len: int
    tool_schemas: list[dict]

    new_message_ids: list[str] = field(default_factory=list)

    # 每轮 reset
    iteration_index: int = 0
    message_id: str = ""
    msg_meta: Optional[dict] = None
    text_parts: Optional[list[str]] = None
    accumulated_tool_calls: Optional[dict[int, dict]] = None
    finish_reason: Optional[str] = None
    thinking_segments: Optional[list[dict]] = None

    # BeforeModelRequest hook 写入，主 loop 读取
    provider_messages: Optional[list[dict]] = None

    # 退出信息
    exception: Optional[BaseException] = None
    done_reason: Optional[str] = None  # None / "max_iterations_reached"


HookCallback = Callable[[AgentContext], Optional[Iterable[dict]]]


class HookManager:
    def __init__(self) -> None:
        self._hooks: dict[Event, list[HookCallback]] = defaultdict(list)

    def register(self, event: Event, callback: HookCallback) -> None:
        self._hooks[event].append(callback)

    def trigger(self, event: Event, ctx: AgentContext):
        """按注册顺序触发；回调异常被吞掉打日志，主 loop 不中断。"""
        for cb in self._hooks.get(event, ()):
            try:
                result = cb(ctx)
            except Exception as e:
                logger.warning(
                    "hook %s on %s failed: %s",
                    getattr(cb, "__name__", repr(cb)),
                    event.value,
                    e,
                )
                continue
            if result:
                yield from result
