"""build_hooks：装配 9 个默认 hook 实例，按关键字打包供 HookManager 构造。

触发顺序不再由此处列表表达——已移入 HookManager 各具名方法（字面顺序 + 注释）。
本函数只负责 new + 打包。
"""

from __future__ import annotations

from dataclasses import dataclass

from kitty.hooks.base import Hook
from kitty.hooks.builtin.iteration_start import IterationStartHook
from kitty.hooks.builtin.persistence import PersistenceHook
from kitty.hooks.builtin.rollback import RollbackHook
from kitty.hooks.builtin.sanitizer import SanitizerHook
from kitty.hooks.builtin.system_prompt import SystemPromptHook
from kitty.hooks.builtin.text_response import TextResponseHook
from kitty.hooks.builtin.title import TitleHook
from kitty.hooks.builtin.tool_call import ToolCallHook
from kitty.hooks.builtin.trace import TraceHook
from kitty.services.session import SessionService
from kitty.services.system_prompt_builder import SystemPromptBuilder
from kitty.services.title import TitleGenerationService
from kitty.tools.base import ToolCtxFactory, ToolRegistry


@dataclass(frozen=True)
class HookBundle:
    sys_prompt: Hook
    iteration_start: Hook
    sanitizer: Hook
    trace: TraceHook
    text_response: Hook
    tool_call: Hook
    persistence: Hook
    title: Hook
    rollback: Hook


def build_hooks(
    session_service: SessionService,
    system_prompt_builder: SystemPromptBuilder,
    title_service: TitleGenerationService,
    model_id: str,
    max_tokens: int,
    tool_registry: ToolRegistry,
    tool_ctx_factory: ToolCtxFactory,
) -> HookBundle:
    return HookBundle(
        sys_prompt=SystemPromptHook(session_service),
        iteration_start=IterationStartHook(),
        sanitizer=SanitizerHook(session_service, system_prompt_builder),
        trace=TraceHook(session_service, model_id, max_tokens),
        text_response=TextResponseHook(session_service),
        tool_call=ToolCallHook(session_service, tool_registry, tool_ctx_factory),
        persistence=PersistenceHook(),
        title=TitleHook(session_service, title_service),
        rollback=RollbackHook(session_service),
    )
