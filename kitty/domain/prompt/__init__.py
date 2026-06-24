# kitty/domain/prompt/__init__.py
"""prompt 装配包：supervisor + subagent prompt 同住一处。

子 Agent prompt 不进 task 包，与 supervisor prompt 聚于此；prompt 包不 import task
的运行时逻辑（只 import task 的纯模型 profiles——单向，无环）。
"""
from __future__ import annotations

from kitty.domain.prompt.subagent import build_subagent_system_prompt
from kitty.domain.prompt.supervisor import SYSTEM_PROMPT, PromptContext, build_system_prompt

__all__ = ["SYSTEM_PROMPT", "PromptContext", "build_system_prompt", "build_subagent_system_prompt"]
