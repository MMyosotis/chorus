"""轮首气泡边界通知：supervisor 专属，发 MessageStartEvent 让前端建新气泡。

每轮 reset 后由 kernel 触发 TurnStart 事件，本钩子注册时绑 source="supervisor"——subagent
不连 SSE、不注册此钩子，其 TurnStart 触发无回调响应。失败只记日志不阻断（通知性质，与
trace 同类，非主业务）。
"""

from __future__ import annotations

from typing import Iterator

from chorus.agents.runtime import AgentContext
from chorus.domain.events import MessageStartEvent, SseEvent


def emit_message_start(ctx: AgentContext, *args: object) -> Iterator[SseEvent]:
    """发气泡边界事件，前端据 message_id 建新气泡并归位后续流式片段。"""
    yield MessageStartEvent(id=ctx.turn.message_id)
