"""异常收尾 hook：append 一条 [Error] assistant 消息关闭本轮（不删数据，不 yield）。

失败轮的 assistant 本就还没入库（入库在轮末核心侧），故库内天然干净；用 [Error]
消息关闭本轮，避免下次出现连续两条 user 消息被 provider 拒。ErrorEvent（前端 SSE）
由 loop 核心侧 yield，本 hook 只做收尾落库。经 trigger fail-open：若收尾落库也
失败，只记日志，loop 仍 yield ErrorEvent。
"""

from __future__ import annotations

from typing import Iterable

from kitty.agents.runtime import AgentContext
from kitty.domain.events import SseEvent
from kitty.services.message import MessageService


class ErrorFinalizer:
    """异常收尾：把异常轮用一条 [Error] 占位 assistant 消息关闭。"""

    def __init__(self, message_service: MessageService):
        self._message = message_service

    def on_error(self, ctx: AgentContext) -> Iterable[SseEvent]:
        # 仅当本轮已分配 message_id 时关闭该轮（异常发生在分配 message_id 之前则跳过）
        if ctx.turn.message_id:
            self._message.append_assistant_message(
                ctx.session_id,
                message_id=ctx.turn.message_id,
                content=f"[Error] {ctx.outcome.exception}",
                tool_calls=[],
            )
        return None
