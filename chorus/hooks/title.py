"""收尾钩子：首轮回复后生成短标题并发出更新事件。

失败不阻断主流程。已定名会话短路，避免重复生成。
"""

from __future__ import annotations

from typing import Iterable, Optional

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent, TitleUpdateEvent
from chorus.domain.message import first_user_text
from chorus.domain.title import TitleGenerationService
from chorus.services.message import MessageService
from chorus.services.session import SessionService


class TitlePostProcessor:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        title_service: TitleGenerationService,
    ):
        self._session = session_service
        self._message = message_service
        self._title = title_service

    def on_stop(self, ctx: AgentContext) -> Optional[Iterable[SseEvent]]:
        # 已定名则短路，不调模型不遍历历史
        if self._session.is_title_set(ctx.session_id):
            return None
        user_text = self._first_user(ctx.session_id)
        title = self._title.generate(user_text)
        if not title:
            return None
        if not self._session.set_title(ctx.session_id, title):
            return None
        return [TitleUpdateEvent(id=ctx.session_id, title=title)]

    def _first_user(self, session_id: str) -> str:
        return first_user_text(self._message.list_messages(session_id))
