"""扁平钩子注册表：事件到回调列表，循环只调触发。

钩子是挂在循环上的扩展点，不是主业务承载点。触发只做观测，逐回调失败只记日志不阻断；
策略拦截类钩子为未来扩展点。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterator

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent

logger = logging.getLogger(__name__)

# 钩子回调：接收上下文与参数，返回事件序列或空
HookFn = Callable[..., Any]

# agent loop 的事件点
EVENTS = (
    "BeforeModelRequest",  # 调模型前
    "AfterModelResponse",  # 流式消费完、分流前
    "PreToolUse",          # 单个工具执行前
    "PostToolUse",         # 单个工具执行后
    "Stop",                # 文本回复落库后、收尾前
    "Error",               # 异常上抛后、发错误前
)


class HookRegistry:
    """事件到回调列表的扁平注册表，触发分发时失败不阻断。"""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = {e: [] for e in EVENTS}

    def register(self, event: str, fn: HookFn) -> None:
        if event not in self._hooks:
            raise ValueError(f"未知 hook 事件: {event!r}（已知: {EVENTS}）")
        self._hooks[event].append(fn)

    def trigger(self, event: str, ctx: AgentContext, *args: Any, **kwargs: Any) -> Iterator[SseEvent]:
        """按注册顺序调用该事件的所有回调，产出其事件；单回调抛错只记日志跳过。"""
        for fn in self._hooks.get(event, ()):
            try:
                result = fn(ctx, *args, **kwargs)
            except Exception as e:  # noqa: BLE001 — 扩展 hook fail-open
                logger.warning("hook %s on %s failed: %s", getattr(fn, "__self__", fn), event, e)
                continue
            if result is not None:
                yield from result
