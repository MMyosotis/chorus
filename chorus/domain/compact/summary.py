"""摘要生成：非流式一次调用压缩历史。"""
from __future__ import annotations

from typing import Optional

from openai import OpenAI

from chorus.domain.bypass import call_once
from chorus.domain.log import get_logger
from chorus.domain.message import Message

_logger = get_logger("domain.compact")

_SUMMARY_INPUT_MAX_CHARS = 120_000
_SUMMARY_MAX_TOKENS = 4096

_SUMMARY_INSTRUCTION = (
    "请把下面的对话历史压缩成一份摘要，供创作流程续接使用。保留：\n"
    "1. 当前创作主题与意图进展（推进到哪一步）\n"
    "2. 已确认的任务图与各步结论\n"
    "3. 用户在本会话内的明确约束与偏好\n"
    "4. 当前进展与剩余工作\n"
    "创作者记忆档案由系统另行注入，不要复述其内容。只输出摘要正文。"
)


class SummaryGenerationService:
    """非流式一次调用生成历史摘要，失败返 None 由调用方降级。"""

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def summarize(self, messages: list[Message]) -> Optional[str]:
        lines = [msg.to_history_line() for msg in messages]
        conversation = "\n".join(lines)[:_SUMMARY_INPUT_MAX_CHARS]
        prompt = f"{_SUMMARY_INSTRUCTION}\n\n{conversation}"
        try:
            return call_once(self._client, self._model, prompt, _SUMMARY_MAX_TOKENS)
        except Exception:
            _logger.exception("compact summary failed")
            return None
