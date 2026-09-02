"""输入建议：替用户起草下一句要发的话术的旁路生成。

纯函数筛近期对话并拼装提示词；生成服务非流式调一次模型，失败返空列表降级。
"""
from __future__ import annotations

from typing import Iterable

from openai import OpenAI

from chorus.domain.bypass import call_once
from chorus.domain.intent import IntentState, intent_state_block
from chorus.domain.log import get_logger
from chorus.domain.message import Message, recent_chat_block

_logger = get_logger("domain.suggestion")

_MAX_SUGGESTIONS = 3
_MAX_TOKENS = 512


def build_suggestion_prompt(state: IntentState, messages: Iterable[Message]) -> str:
    """拼装旁路提示词：意图快照加近期对话，要求以用户口吻产出 3 条候选输入。"""
    return (
        "你是图文创作助手的输入建议器。根据下方会话现状，替用户起草接下来最想发的 3 句话。\n"
        "要求：\n"
        "- 每条都是用户口吻的输入，可直接作为用户的下一条消息发送，不是对用户的解释或建议说明\n"
        "- 结合会话进展判断内容：还没定主题就给创作方向，主题已定就给细化补充，成品已出就给修改迭代\n"
        "- 严格输出 3 条，每条一行，不要编号、引号或任何额外文字\n\n"
        f"{intent_state_block(state)}\n\n"
        f"{recent_chat_block(messages)}"
    )


def parse_suggestions(raw: str) -> list[str]:
    """按行取建议：滤空行，最多 3 条。"""
    lines = [line.strip() for line in raw.splitlines()]
    return [text for text in lines if text][:_MAX_SUGGESTIONS]


class SuggestionGenerationService:
    """非流式一次调用产出输入建议，失败返空列表交前端降级。"""

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def generate(self, state: IntentState, messages: Iterable[Message]) -> list[str]:
        prompt = build_suggestion_prompt(state, messages)
        try:
            raw = call_once(self._client, self._model, prompt, _MAX_TOKENS)
        except Exception:
            _logger.exception("suggestion generation failed")
            return []
        return parse_suggestions(raw)
