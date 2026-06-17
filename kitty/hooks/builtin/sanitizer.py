"""BeforeModelRequest hook：构建传给 LLM 的消息序列（plan 检验1 的唯一构建点）。

不再就地剥字段 —— 调 SessionService.build_provider_messages（它从 messages 表
按 seq 读取并组装 [system] + 历史），写入 ctx.turn.provider_messages 供主循环消费。
"""

from __future__ import annotations

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent
from kitty.hooks.base import Hook
from kitty.services.session import SessionService
from kitty.services.system_prompt_builder import SystemPromptBuilder


class SanitizerHook(Hook):
    def __init__(
        self,
        session_service: SessionService,
        system_prompt_builder: SystemPromptBuilder,
    ):
        self._session = session_service
        self._prompt_builder = system_prompt_builder

    def handle(self, ctx: AgentContext) -> list[SseEvent] | None:
        ctx.turn.provider_messages = self._session.build_provider_messages(
            ctx.session_id, self._prompt_builder.build()
        )
        return None
