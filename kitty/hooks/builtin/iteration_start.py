"""IterationStart hook：分配本轮 message_id，yield message_start。"""

from __future__ import annotations

import uuid

from kitty.domain.agent import AgentContext
from kitty.domain.events import MessageStartEvent, SseEvent
from kitty.hooks.base import Hook


class IterationStartHook(Hook):
    def handle(self, ctx: AgentContext) -> list[SseEvent] | None:
        message_id = uuid.uuid4().hex
        ctx.turn.message_id = message_id
        ctx.rollback.record(message_id)
        return [MessageStartEvent(id=message_id)]
