"""BeforeModelRequest hook：构建传给 LLM 的消息序列（plan 检验1 的唯一构建点）。

不再就地剥字段 —— 调 SessionService.build_provider_messages（它从 messages 表
按 seq 读取并组装 [system] + 历史），写入 ctx.turn.provider_messages 供主循环消费。
system prompt 的多方信息收集（base + skill 摘要）在本 hook 完成（编排层），
拼装规则在 domain.services.prompt.build_system_prompt。
"""

from __future__ import annotations

from kitty.domain.models.agent import AgentContext
from kitty.domain.models.events import SseEvent
from kitty.domain.services.prompt import PromptContext, build_system_prompt
from kitty.hooks.base import Hook
from kitty.services.session import SessionService
from kitty.services.skill import SkillService


class SanitizerHook(Hook):
    def __init__(
        self,
        session_service: SessionService,
        system_prompt: str,
        skill_service: SkillService,
    ):
        self._session = session_service
        self._system_prompt = system_prompt
        self._skill = skill_service

    def handle(self, ctx: AgentContext) -> list[SseEvent] | None:
        prompt = build_system_prompt(PromptContext(
            base=self._system_prompt,
            skill_hints=self._skill.format_hints(),
        ))
        ctx.turn.provider_messages = self._session.build_provider_messages(
            ctx.session_id, prompt
        )
        return None
