"""hook 子系统：CC 式扁平注册表（event → list[callable]）+ 三个扩展 handler。

观测（TraceEmitter）/ 收尾（TitlePostProcessor）/ 异常恢复（RollbackHandler）；
经 HookRegistry.trigger 调用，fail-open。主流程在 SupervisorService.stream()，不在此处。
"""

from __future__ import annotations

from kitty.hooks.registry import EVENTS, HookFn, HookRegistry
from kitty.hooks.rollback import RollbackHandler
from kitty.hooks.title import TitlePostProcessor
from kitty.hooks.trace import TraceEmitter

__all__ = [
    "HookRegistry",
    "HookFn",
    "EVENTS",
    "TraceEmitter",
    "TitlePostProcessor",
    "RollbackHandler",
]
