"""记忆旁路 LLM 服务：提取 / 合并去重 / 召回选择，失败抛异常交编排层。"""
from __future__ import annotations

from openai import OpenAI

from chorus.domain.bypass import call_once
from chorus.domain.memory.models import CreatorMemory, MemoryDigest, MemoryDraft
from chorus.domain.memory.prompts import (
    build_consolidate_prompt,
    build_extract_prompt,
    build_recall_prompt,
    parse_json_array,
)
from chorus.domain.message import Message

_MAX_RECALL = 5


class MemoryLLMService:
    """非流式一次调用，产草稿（提取与合并）或选标识（召回），失败抛异常交编排层。"""

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def extract(self, history: list[Message], existing: list[CreatorMemory]) -> list[MemoryDraft]:
        return self._drafts(build_extract_prompt(history, existing))

    def merge(self, memories: list[CreatorMemory]) -> list[MemoryDraft]:
        return self._drafts(build_consolidate_prompt(memories))

    def select(self, digest: MemoryDigest, task_hint: str) -> list[str]:
        if digest.is_empty:
            return []
        items = self._raw_items(build_recall_prompt(digest, task_hint), 512)
        return [item for item in items if isinstance(item, str)][:_MAX_RECALL]

    def _drafts(self, prompt: str) -> list[MemoryDraft]:
        items = self._raw_items(prompt, 4096)
        return [MemoryDraft(**item) for item in items if isinstance(item, dict)]

    def _raw_items(self, prompt: str, max_tokens: int) -> list:
        return parse_json_array(call_once(self._client, self._model, prompt, max_tokens))
