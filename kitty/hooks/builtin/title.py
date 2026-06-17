"""AssistantTextResponse hook（done 之后）：首轮生成短标题 + yield title_update。

注册顺序在 TextResponseHook 之后：前端收到 done 已解锁，title_update 是补丁式后续事件。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent, TitleUpdateEvent
from kitty.domain.models.message import AssistantMessage, UserMessage
from kitty.hooks.base import Hook
from kitty.services.session import SessionService
from kitty.services.title import TitleGenerationService


class TitleHook(Hook):
    def __init__(
        self,
        session_service: SessionService,
        title_service: TitleGenerationService,
    ):
        self._session = session_service
        self._title = title_service

    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        first_user, first_assistant = self._first_pair(ctx.session_id)
        title = self._title.generate(first_user, first_assistant)
        if not title:
            return None
        if not self._session.set_title_if_unset(ctx.session_id, title):
            return None
        return [TitleUpdateEvent(id=ctx.session_id, title=title)]

    def _first_pair(self, session_id: str) -> tuple[str, str]:
        first_user = ""
        first_assistant = ""
        for m in self._session.list_messages(session_id):
            if isinstance(m, UserMessage) and not first_user:
                first_user = m.content
            elif isinstance(m, AssistantMessage) and (m.content or "").strip() and not first_assistant:
                first_assistant = m.content or ""
            if first_user and first_assistant:
                break
        return first_user, first_assistant
