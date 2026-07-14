"""钩子系统：扁平注册表加两个处理器——观测、标题收尾。

经注册表触发调用，失败不阻断主流程。主流程在各 agent loop 内，不在此处。
"""

from __future__ import annotations

from chorus.hooks.registry import EVENTS, HookFn, HookRegistry
from chorus.hooks.title import TitlePostProcessor
from chorus.hooks.trace import TraceEmitter

__all__ = [
    "HookRegistry",
    "HookFn",
    "EVENTS",
    "TraceEmitter",
    "TitlePostProcessor",
]
