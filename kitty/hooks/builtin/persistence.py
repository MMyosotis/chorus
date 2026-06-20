"""Persistence hook：逐条入库后，工具分支轮末无需 save；仅 LoopEnd 兜底 yield done。

阶段 2 起 message 逐条 append 入库（见 plan M2），本 hook 不再负责全量重写。
保留 on_loop_end 在达到 MAX_TOOL_ITERATIONS 时 yield done(reason)。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.agent import AgentContext
from kitty.domain.events import DoneEvent, SseEvent
from kitty.hooks.base import Hook


class PersistenceHook(Hook):
    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        return [DoneEvent(reason=ctx.outcome.done_reason or "max_iterations_reached")]
