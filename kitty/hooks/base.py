"""Hook 基类：子类 override handle(ctx) 响应自己关心的事件。

TraceHook 例外——它响应多个事件，暴露多个具名方法（见 trace.py），
由 HookManager 对应的具名方法分别调用。

返回 Iterable[SseEvent] | None；非 None 的部分会被主 loop yield 给前端。
HookManager 按字面顺序调用各 hook，单个 hook 异常被吞掉打日志（fail-open）。
"""

from __future__ import annotations

from typing import Iterable

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent


class Hook:
    name: str = ""

    def handle(self, ctx: AgentContext) -> Iterable[SseEvent] | None:
        raise NotImplementedError
