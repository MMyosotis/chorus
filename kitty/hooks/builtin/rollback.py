"""LoopError hook：回滚本轮新增消息 + 对应 trace，yield error。

回滚锚点 = ctx.history_snapshot_len（入口前 messages 数量）；
同时删除本轮 new_message_ids 的 trace，保证库内不留半截回合。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.agent import AgentContext
from kitty.domain.events import ErrorEvent, SseEvent
from kitty.hooks.base import Hook
from kitty.services.session import SessionService


class RollbackHook(Hook):
    def __init__(self, session_service: SessionService):
        self._session = session_service

    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        self._session.truncate_after_snapshot(
            ctx.session_id, ctx.history_snapshot_len, ctx.rollback.new_message_ids
        )
        return [ErrorEvent(content=str(ctx.outcome.exception))]
