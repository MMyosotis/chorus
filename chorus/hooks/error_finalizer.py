"""异常收尾钩子：追加一条错误占位助手消息关闭本轮，不删数据不发事件。

失败轮助手消息尚未入库，库内天然干净；用占位消息关闭本轮避免连续两条用户消息被拒。
错误事件由循环发出，本钩子只做收尾落库，失败只记日志。
"""

from __future__ import annotations

from typing import Iterable

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent
from chorus.services.message import MessageService


class ErrorFinalizer:
    """异常收尾：用一条错误占位助手消息关闭异常轮。"""

    def __init__(self, message_service: MessageService):
        self._message = message_service

    def on_error(self, ctx: AgentContext) -> Iterable[SseEvent]:
        # 仅当本轮已分配消息标识时关闭，否则跳过
        if ctx.turn.message_id:
            self._message.append_assistant_message(
                ctx.session_id,
                message_id=ctx.turn.message_id,
                content=f"[Error] {ctx.outcome.exception}",
                tool_calls=[],
            )
        return None
