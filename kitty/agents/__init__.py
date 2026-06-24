# kitty/agents/__init__.py
"""agents 顶层包：agent loop 编排子系统（与 tools/ 对称）。

本计划只建 runtime 脚手架；supervisor/subagent/scheduler 在计划 2 加入。
"""
from __future__ import annotations

from kitty.agents.runtime import AgentContext, LoopOutcome, TurnState

__all__ = ["AgentContext", "LoopOutcome", "TurnState"]
