"""扁平钩子注册表：事件到回调列表，循环只调触发，失败不阻断。

register 可带 source 绑定特定 agent，trigger 按 source 过滤——先专属再全局。
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, Optional

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent
from chorus.domain.log import ctx_fields, get_logger

_logger = get_logger("hook")

HookFn = Callable[..., Any]

EVENTS = (
    "BeforeModelRequest",
    "AfterModelResponse",
    "PreToolUse",
    "PostToolUse",
    "Stop",
)


class HookRegistry:
    """事件到回调列表的扁平注册表，触发分发时失败不阻断。

    register 可带 source 绑定特定 agent（如 ``source="supervisor"``），trigger 时按
    ``ctx.source`` 过滤：先调 source 专属回调，再调全局回调（source=None）。未绑 source
    的回调对所有 agent 触发。
    """

    def __init__(self) -> None:
        # 键 (event, source)：source=None 表示全局，source="supervisor"/"subagent" 表示专属
        self._hooks: dict[tuple[str, Optional[str]], list[HookFn]] = {}

    def register(self, event: str, fn: HookFn, *, source: Optional[str] = None) -> None:
        if event not in EVENTS:
            raise ValueError(f"未知 hook 事件: {event!r}（已知: {EVENTS}）")
        self._hooks.setdefault((event, source), []).append(fn)

    def trigger(self, event: str, ctx: AgentContext, *args: Any, **kwargs: Any) -> Iterator[SseEvent]:
        """按 source 专属 → 全局顺序调用回调，产出其事件；单回调抛错跳过不阻断。"""
        for source in (ctx.source, None):
            yield from self._trigger_source(event, source, ctx, *args, **kwargs)

    def _trigger_source(
        self, event: str, source: Optional[str], ctx: AgentContext, *args: Any, **kwargs: Any,
    ) -> Iterator[SseEvent]:
        """调用单个 source 作用域下注册的回调；单回调抛错跳过不阻断。"""
        for fn in self._hooks.get((event, source), ()):
            try:
                result = fn(ctx, *args, **kwargs)
            except Exception:  # noqa: BLE001 — 扩展 hook fail-open
                _logger.exception("hook callback failed", extra={**ctx_fields(ctx), "hook_event": event})
                continue
            if result is not None:
                yield from result
