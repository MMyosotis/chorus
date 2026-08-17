"""记忆旁路 LLM 服务：提取 / 合并去重 / 召回选择；格式不对喂回自纠最多 3 次，仍败上抛交编排层降级。"""
from __future__ import annotations

from openai import OpenAI
from pydantic import ValidationError

from chorus.domain.bypass import call_once
from chorus.domain.log import get_logger
from chorus.domain.memory.models import CreatorMemory, MemoryDigest, MemoryDraft
from chorus.domain.memory.prompts import (
    build_consolidate_prompt,
    build_extract_prompt,
    build_recall_prompt,
    parse_drafts,
    parse_json_array,
)
from chorus.domain.message import Message

_logger = get_logger("domain.memory.llm")

_MAX_RECALL = 5
_MAX_RETRIES = 3


class MemoryLLMService:
    """非流式一次调用，产草稿（提取与合并）或选标识（召回）；格式不对喂回自纠。"""

    # 按提取/合并的最大输出配额
    _MAX_TOKENS = 8192

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def extract(self, history: list[Message], existing: list[CreatorMemory]) -> list[MemoryDraft]:
        return self._drafts("extract", build_extract_prompt(history, existing))

    def merge(self, memories: list[CreatorMemory]) -> list[MemoryDraft]:
        return self._drafts("merge", build_consolidate_prompt(memories))

    def select(self, digest: MemoryDigest, task_hint: str) -> list[str]:
        if digest.is_empty:
            return []
        items = self._call_with_retry(
            "recall", build_recall_prompt(digest, task_hint), self._MAX_TOKENS, parse_json_array
        )
        return [item for item in items if isinstance(item, str)][:_MAX_RECALL]

    def _drafts(self, label: str, prompt: str) -> list[MemoryDraft]:
        return self._call_with_retry(label, prompt, self._MAX_TOKENS, parse_drafts)

    def _call_with_retry(self, label: str, prompt: str, max_tokens: int, parse) -> list:
        """调模型并解析；调模型异常直接上抛，格式不对喂回自纠最多 3 次。"""
        correction = ""
        last_exc: Exception | None = None
        attempts = 0
        while attempts < _MAX_RETRIES:
            raw = self._invoke(label, prompt + correction, max_tokens)
            try:
                return parse(raw)
            except (ValueError, ValidationError) as exc:
                _logger.debug("memory bypass %s parse failed, retry", label, exc_info=True)
                correction = f"\n\n上次输出无法解析：{exc}。请只返回合法 JSON 数组，不要任何其他文字。"
                last_exc = exc
            attempts += 1

        _logger.warning("memory bypass %s retry exhausted", label, exc_info=last_exc)
        raise RuntimeError(f"记忆旁路自纠 {_MAX_RETRIES} 次仍失败")

    def _invoke(self, label: str, prompt: str, max_tokens: int) -> str:
        """调模型，异常记栈后上抛。"""
        try:
            return call_once(self._client, self._model, prompt, max_tokens)
        except Exception:
            _logger.exception("memory bypass %s api call failed", label)
            raise
