"""提示词装配包：每个 agent 一个模块，打开即见该 agent 全部上下文注入位置；装配机制在 assembly。"""
from __future__ import annotations

from chorus.domain.prompt.subagent import (
    SubagentSystemInputs,
    SubagentUserInputs,
    SkeletonInputs,
    InvokeInputs,
    build_task_content,
    subagent_base,
)
from chorus.domain.prompt.supervisor import (
    SYSTEM_PROMPT,
    SupervisorSystemInputs,
    SupervisorUserInputs,
)

__all__ = [
    "SYSTEM_PROMPT",
    "SubagentSystemInputs",
    "SubagentUserInputs",
    "SkeletonInputs",
    "InvokeInputs",
    "build_task_content",
    "SupervisorSystemInputs",
    "SupervisorUserInputs",
    "subagent_base",
]
