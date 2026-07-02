"""提示词装配包：主调度与子角色的提示词同住一处。"""
from __future__ import annotations

from chorus.domain.prompt.subagent import build_subagent_system_prompt
from chorus.domain.prompt.supervisor import SYSTEM_PROMPT, PromptContext, build_system_prompt

__all__ = ["SYSTEM_PROMPT", "PromptContext", "build_system_prompt", "build_subagent_system_prompt"]
