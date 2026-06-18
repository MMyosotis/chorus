"""LoopStart hook：把本轮用户消息追加入库。

system 消息不持久化（每次由 SanitizerHook 调 build_system_prompt 现拼，
build_provider_messages 注入），故本 hook 只负责 append user message。
history_snapshot_len 由 ChatService 在入口前（append 之前）算好填入 ctx，作为回滚锚点。
"""

from __future__ import annotations

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent
from kitty.hooks.base import Hook
from kitty.services.session import SessionService


class SystemPromptHook(Hook):
    def __init__(self, session_service: SessionService):
        self._session = session_service

    def handle(self, ctx: AgentContext) -> list[SseEvent] | None:
        self._session.append_user_message(ctx.session_id, ctx.user_message)
        return None
