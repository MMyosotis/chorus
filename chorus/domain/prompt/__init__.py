"""提示词装配包：每个 agent 一个模块，打开即见该 agent 全部上下文注入位置；装配机制在 assembly。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from chorus.domain.prompt.assembly import (
    TaggedSegment,
    build_system_prompt,
    inject_user_blocks,
    parse_tagged_content,
    tagged_block,
)

if TYPE_CHECKING:
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
        SupervisorUserInputs,
    )

__all__ = [
    "SYSTEM_PROMPT",
    "TaggedSegment",
    "SubagentSystemInputs",
    "SubagentUserInputs",
    "SkeletonInputs",
    "InvokeInputs",
    "build_system_prompt",
    "build_task_content",
    "inject_user_blocks",
    "parse_tagged_content",
    "subagent_base",
    "SupervisorUserInputs",
    "tagged_block",
]


def __getattr__(name: str):
    """懒加载各 agent 装配模块以破循环导入：trace 域引用装配机制，顶层导入会经 memory 成环。"""
    if name == "SYSTEM_PROMPT":
        from chorus.domain.prompt.supervisor import SYSTEM_PROMPT
        return SYSTEM_PROMPT
    if name == "SubagentSystemInputs":
        from chorus.domain.prompt.subagent import SubagentSystemInputs
        return SubagentSystemInputs
    if name == "SubagentUserInputs":
        from chorus.domain.prompt.subagent import SubagentUserInputs
        return SubagentUserInputs
    if name == "SkeletonInputs":
        from chorus.domain.prompt.subagent import SkeletonInputs
        return SkeletonInputs
    if name == "InvokeInputs":
        from chorus.domain.prompt.subagent import InvokeInputs
        return InvokeInputs
    if name == "build_task_content":
        from chorus.domain.prompt.subagent import build_task_content
        return build_task_content
    if name == "subagent_base":
        from chorus.domain.prompt.subagent import subagent_base
        return subagent_base
    if name == "SupervisorUserInputs":
        from chorus.domain.prompt.supervisor import SupervisorUserInputs
        return SupervisorUserInputs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
