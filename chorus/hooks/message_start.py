"""轮首气泡边界通知：supervisor 专属，发事件让前端建新气泡。

注册时绑 supervisor，subagent 不连 SSE 不注册；通知性质，失败只记日志。
"""

from __future__ import annotations

from typing import Iterator

from chorus.agents.runtime import AgentContext
from chorus.domain.events import MessageStartEvent, SseEvent


def emit_message_start(ctx: AgentContext, *args: object) -> Iterator[SseEvent]:
    """发气泡边界事件，前端据 message_id 建新气泡并归位后续流式片段。"""
    yield MessageStartEvent(id=ctx.turn.message_id)
