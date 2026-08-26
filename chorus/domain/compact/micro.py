"""微压缩：旧工具结果滑出最近窗口后正文换省略占位，行留原位保住工具配对。"""
from __future__ import annotations

from chorus.domain.message import Message, ToolMessage

TOOL_PLACEHOLDER = "[旧工具结果已省略]"

_KEEP_RECENT_TOOL_RESULTS = 3
_TOOL_PLACEHOLDER_MIN_LEN = 120


def apply_micro(messages: list[Message]) -> tuple[list[Message], list[str]]:
    """超长旧工具结果正文换占位，附换掉的标识；已是占位的行因过短自动不再入选。"""
    elided = _plan(messages)
    if not elided:
        return messages, []
    marked = set(elided)
    return [
        msg.model_copy(update={"content": TOOL_PLACEHOLDER}) if msg.id in marked else msg
        for msg in messages
    ], elided


def _plan(messages: list[Message]) -> list[str]:
    tool_indices = [idx for idx, msg in enumerate(messages) if isinstance(msg, ToolMessage)]
    return [
        messages[idx].id
        for idx in tool_indices[:-_KEEP_RECENT_TOOL_RESULTS]
        if len(messages[idx].content or "") > _TOOL_PLACEHOLDER_MIN_LEN
    ]
