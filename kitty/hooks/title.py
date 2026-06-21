"""收尾 hook：首轮 assistant 文本回复后生成短标题 + yield title_update。

原 TitleHook 逻辑去掉 Hook ABC。失败 fail-open（经 trigger）：标题生成/落库失败
只记日志，不影响主流程 done。读历史消息走 MessageService，落标题走 SessionService。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.agent import AgentContext
from kitty.domain.events import SseEvent, TitleUpdateEvent
from kitty.domain.message import AssistantMessage, UserMessage
from kitty.domain.title import TitleGenerationService
from kitty.services.message import MessageService
from kitty.services.session import SessionService


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
        for m in self._message.list_messages(session_id):
            if isinstance(m, UserMessage) and not first_user:
                first_user = m.content
            elif isinstance(m, AssistantMessage) and (m.content or "").strip() and not first_assistant:
                first_assistant = m.content or ""
            if first_user and first_assistant:
                break
        return first_user, first_assistant
