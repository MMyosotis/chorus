"""提示词装配包：主调度基础文案与子角色模板同住，条件段经装配入口统一拼入。"""
from __future__ import annotations

from chorus.domain.prompt.assembly import PromptContext, build_system_prompt
from chorus.domain.prompt.subagent import subagent_base
from chorus.domain.prompt.supervisor import SYSTEM_PROMPT

__all__ = ["SYSTEM_PROMPT", "PromptContext", "build_system_prompt", "subagent_base"]
