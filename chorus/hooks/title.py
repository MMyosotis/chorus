"""收尾钩子：首轮回复后生成短标题并发出更新事件。

失败只记日志不阻断主流程。已定名会话短路，避免重复生成。
"""

from __future__ import annotations

from typing import Iterable

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent, TitleUpdateEvent
from chorus.domain.message import AssistantMessage, UserMessage
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

    def on_stop(self, ctx: AgentContext) -> Iterable[SseEvent]:
        # 已定名则短路，不调模型不遍历历史
        if self._session.is_title_set(ctx.session_id):
            return None
        first_user, first_assistant = self._first_pair(ctx.session_id)
        title = self._title.generate(first_user, first_assistant)
        if not title:
            return None
        if not self._session.set_title(ctx.session_id, title):
            return None
        return [TitleUpdateEvent(id=ctx.session_id, title=title)]

    def _first_pair(self, session_id: str) -> tuple[str, str]:
        first_user = ""
        first_assistant = ""
        for m in self._message.list_messages(session_id):
            if isinstance(m, UserMessage) and not first_user:
                first_user = m.content
            elif isinstance(m, AssistantMessage) and (m.content or "").strip() and not first_assistant:
                first_assistant = m.content or ""
            if first_user and first_assistant:
                break
        return first_user, first_assistant
