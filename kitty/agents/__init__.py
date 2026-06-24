# kitty/agents/__init__.py
"""agents 顶层包：agent loop 编排子系统（与 tools/ 对称）。

本计划只建 runtime 脚手架；supervisor/subagent/scheduler 在计划 2 加入。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kitty.agents.runtime import AgentContext, LoopOutcome, TurnState

if TYPE_CHECKING:
    # 仅类型注解用，运行时不导入（避免与下面的懒加载重复）。
    from kitty.agents.subagent import SubAgentService

__all__ = ["AgentContext", "LoopOutcome", "TurnState", "SubAgentService"]


def __getattr__(name: str):
    """懒加载 SubAgentService 以破循环导入。

    subagent 依赖 hooks，而 hooks.registry 为 AgentContext 类型注解 import
    agents.runtime——若在此处顶层 import subagent，会形成
    hooks→agents.__init__→subagent→hooks(部分初始化) 的环。改用 PEP 562 模块级
    __getattr__ 延迟到首次访问时导入，re-export 语义不变（from kitty.agents import
    SubAgentService 仍可用），环被打破。supervisor（计划 2 Task 5）同此约束。
    """
    if name == "SubAgentService":
        from kitty.agents.subagent import SubAgentService
        return SubAgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
