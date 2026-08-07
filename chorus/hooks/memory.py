"""记忆提取收尾钩子：主调度回合结束后提取长期记忆并触发整理。

经注册表挂 Stop 事件，失败不阻断主流程。
"""
from __future__ import annotations

from typing import Iterable

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent
from chorus.services.memory import MemoryService


class MemoryExtractor:
    def __init__(self, memory_service: MemoryService):
        self._memory = memory_service

    def on_stop(self, ctx: AgentContext) -> Iterable[SseEvent]:
        self._memory.extract(ctx.session_id)
        return None
