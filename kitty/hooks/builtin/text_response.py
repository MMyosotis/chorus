"""AssistantTextResponse hook：把 assistant 文本回复追加入库 + yield done。

注册顺序在 TraceHook 之后（trace 的 model_response 先到前端），在 TitleHook 之前
（done 先让前端解锁，title 随后补丁式到达）。逐条入库后无需额外 save。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.agent import AgentContext
from kitty.domain.events import DoneEvent, SseEvent
from kitty.hooks.base import Hook
from kitty.services.session import SessionService


class TextResponseHook(Hook):
    def __init__(self, session_service: SessionService):
        self._session = session_service

    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
        self._session.append_assistant_message(
            ctx.session_id,
            message_id=ctx.turn.message_id,
            content=content,
            tool_calls=[],
        )
        return [DoneEvent()]
