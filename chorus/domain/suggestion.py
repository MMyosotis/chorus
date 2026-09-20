"""输入建议：生成可点击的短标题及其对应完整输入内容。"""
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, Field, ValidationError

from chorus.domain.bypass import BypassCaller, BypassScope
from chorus.domain.intent import IntentState, render_intent_state
from chorus.domain.log import get_logger
from chorus.domain.message import Message, recent_chat_text
from chorus.domain.prompt.assembly import tagged_block

_logger = get_logger("domain.suggestion")

_MAX_SUGGESTIONS = 3
_MAX_TOKENS = 512


class Suggestion(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class _SuggestionsPayload(BaseModel):
    suggestions: list[Suggestion]


def build_suggestion_prompt(state: IntentState, messages: Iterable[Message]) -> str:
    """拼装旁路提示词：给每条完整输入配一个用于气泡展示的短标题。"""
    intent_block = tagged_block(
        "intent_state", f"当前意图状态：\n{render_intent_state(state)}",
    )
    return (
        "你是图文创作助手的输入建议器。根据下方会话现状，替用户起草接下来最想发的 3 句话。\n"
        "要求：\n"
        "- 每条建议包含 title 和 content：title 是展示在点击气泡里的简洁标题，content 是用户口吻的完整输入\n"
        "- title 简洁（约 10 字内），直接说明点击后会做什么\n"
        "- content 可直接作为用户的下一条消息发送，不是对用户的解释或建议说明\n"
        "- 结合会话进展判断内容：还没定主题就给创作方向，主题已定就给细化补充，成品已出就给修改迭代\n"
        "- 严格输出 3 条；只输出合法 JSON，不要 Markdown 代码块、编号或任何额外文字\n"
        "- JSON 格式必须为：{\"suggestions\":[{\"title\":\"...\",\"content\":\"...\"}]}\n\n"
        f"{intent_block}\n\n"
        f"{tagged_block('recent_chat', recent_chat_text(messages))}"
    )


def parse_suggestions(raw: str) -> list[Suggestion]:
    """解析模型 JSON；不合法即整组降级为空。"""
    try:
        payload = _SuggestionsPayload.model_validate_json(raw)
    except ValidationError:
        return []
    return payload.suggestions[:_MAX_SUGGESTIONS]


class SuggestionGenerationService:
    """非流式一次调用产出输入建议，失败返空列表交前端降级。"""

    def __init__(self, bypass: BypassCaller):
        self._bypass = bypass

    def generate(self, state: IntentState, messages: Iterable[Message], scope: BypassScope) -> list[Suggestion]:
        prompt = build_suggestion_prompt(state, messages)
        try:
            raw = self._bypass.call(prompt, _MAX_TOKENS, "suggestion", scope)
        except Exception:
            _logger.exception("suggestion generation failed")
            return []
        return parse_suggestions(raw)
