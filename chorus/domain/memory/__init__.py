"""创作者记忆领域包：模型、可见性判定、prompt 构造、渲染与旁路 LLM 服务。"""
from __future__ import annotations

from chorus.domain.memory.llm import MemoryLLMService
from chorus.domain.memory.models import CreatorMemory, MemoryDigest, MemoryDigestEntry, MemoryDraft
from chorus.domain.memory.predicates import visible_to_agent
from chorus.domain.memory.prompts import (
    build_consolidate_prompt,
    build_extract_prompt,
    build_recall_prompt,
)
from chorus.domain.memory.render import render_digest_block, render_recall_block

__all__ = [
    "CreatorMemory",
    "MemoryDigest",
    "MemoryDigestEntry",
    "MemoryDraft",
    "MemoryLLMService",
    "build_consolidate_prompt",
    "build_extract_prompt",
    "build_recall_prompt",
    "render_digest_block",
    "render_recall_block",
    "visible_to_agent",
]
