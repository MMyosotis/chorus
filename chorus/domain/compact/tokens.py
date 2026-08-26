"""token 估算与溢出判定。"""
from __future__ import annotations

from typing import Iterable

from chorus.domain.message import Message

COMPACT_THRESHOLD_TOKENS = 60_000

_OVERFLOW_MARKERS = (
    "context_length",
    "maximum context length",
    "prompt_too_long",
    "context window",
)


def estimate_tokens(messages: Iterable[Message]) -> int:
    """按字符数粗估 token，中英混排取偏高系数，宁早压勿打爆。"""
    return int(sum(msg.payload_chars() for msg in messages) * 0.75)


def is_context_overflow(error: BaseException) -> bool:
    """判定异常是否为输入超长，供应急压缩识别。"""
    text = str(error).lower()
    return any(marker in text for marker in _OVERFLOW_MARKERS)
