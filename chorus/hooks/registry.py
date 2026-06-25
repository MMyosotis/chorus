"""CC 式扁平 hook 注册表：event → list[callable]，loop 只调 trigger。

遵循「挂在循环上，不写进循环里」：hook 是挂在稳定 loop 上的
扩展点，不是主业务承载点。trigger 观测-only——逐回调 try/except 记日志跳过（fail-open），
不阻断主流程；策略/拦截类 hook（verdict 回编 loop）为未来扩展点，届时再加返回值。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterator

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent

logger = logging.getLogger(__name__)

# hook 回调：接收 (ctx, *args, **kwargs)，返回 Iterable[SseEvent] | None。
HookFn = Callable[..., Any]

# agent loop 的事件点（loop 在这些节点调 trigger）。
EVENTS = (
    "BeforeModelRequest",  # 构造 provider_messages 之后、调 LLM 之前
    "AfterModelResponse",  # 流式消费完、决定走文本/工具之前（两类分支共用）
    "PreToolUse",          # 单个工具执行前
    "PostToolUse",         # 单个工具执行后
    "Stop",                # 文本回复落库后、yield done 前（标题生成）
    "Error",               # 异常上抛后、yield error 前（异常收尾）
)


class HookRegistry:
    """event → list[HookFn] 的扁平注册表 + trigger 分发（fail-open）。"""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = {e: [] for e in EVENTS}

    def register(self, event: str, fn: HookFn) -> None:
        if event not in self._hooks:
            raise ValueError(f"未知 hook 事件: {event!r}（已知: {EVENTS}）")
        self._hooks[event].append(fn)

    def trigger(self, event: str, ctx: AgentContext, *args: Any, **kwargs: Any) -> Iterator[SseEvent]:
        """按注册顺序调用该事件的所有 hook，yield 其返回的事件；单 hook 抛错只记日志、跳过。"""
        for fn in self._hooks.get(event, ()):
            try:
                result = fn(ctx, *args, **kwargs)
            except Exception as e:  # noqa: BLE001 — 扩展 hook fail-open
                logger.warning("hook %s on %s failed: %s", getattr(fn, "__self__", fn), event, e)
                continue
            if result is not None:
                yield from result
