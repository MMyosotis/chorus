"""agents 编排包：三 loop 与运行时脚手架。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from chorus.agents.runtime import AgentContext, LoopOutcome, TurnState

if TYPE_CHECKING:
    from chorus.agents.subagent import SubAgentService
    from chorus.agents.scheduler import TaskScheduler
    from chorus.agents.supervisor import SupervisorService
    from chorus.agents.chat_model import ChatModelEntry

__all__ = [
    "AgentContext", "LoopOutcome", "TurnState",
    "SubAgentService", "TaskScheduler",
    "SupervisorService", "ChatModelEntry",
]


def __getattr__(name: str):
    """懒加载各 loop 以破循环导入：钩子层为类型注解引用运行时，顶层导入会成环。"""
    if name == "SubAgentService":
        from chorus.agents.subagent import SubAgentService
        return SubAgentService
    if name == "TaskScheduler":
        from chorus.agents.scheduler import TaskScheduler
        return TaskScheduler
    if name == "SupervisorService":
        from chorus.agents.supervisor import SupervisorService
        return SupervisorService
    if name == "ChatModelEntry":
        from chorus.agents.chat_model import ChatModelEntry
        return ChatModelEntry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
