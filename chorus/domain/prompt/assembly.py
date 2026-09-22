"""提示词装配机制：条件成段、系统段拼接、条件段注入末条用户消息。

各位置具体拼了哪些段，见 prompt/subagent.py 与 prompt/supervisor.py。
注入段标签是装配与反解共用的词表，控制台视图靠它还原段清单。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

INJECTION_LABELS = {
    "memory_summary": "记忆摘要",
    "available_skills": "可用技能",
    "recalled_memories": "记忆召回",
    "intent_state": "意图状态",
    "recent_chat": "近期对话",
    "role": "角色",
    "step_note": "本步交待",
    "intent": "创作意图",
    "base_card": "底稿",
    "dependency_artifacts": "前置产物",
    "prior_artifact": "上轮产物",
    "user_feedback": "用户反馈",
}

_INJECTION_PATTERN = re.compile(
    f"<({'|'.join(INJECTION_LABELS)})>([\\s\\S]*?)</\\1>"
)


@dataclass(frozen=True)
class TaggedSegment:
    """注入段：中文标签与剥离标签后的正文。"""

    label: str
    content: str


def parse_tagged_content(raw: str) -> tuple[str, list[TaggedSegment]]:
    """反解 tagged_block：返回剥离注入段后的正文与按出现顺序的段清单。"""
    segments = [
        TaggedSegment(INJECTION_LABELS[match.group(1)], match.group(2).strip())
        for match in _INJECTION_PATTERN.finditer(raw)
    ]
    text = _INJECTION_PATTERN.sub("", raw).strip()
    return text, segments


def tagged_block(tag: str, body: Optional[str]) -> str:
    """有正文则包成语义标签块，无正文返空串。"""
    if not body:
        return ""
    return f"<{tag}>\n{body}\n</{tag}>"


def join_sections(sections: list[str]) -> str:
    """按顺序拼接非空文本段。"""
    return "\n\n".join(block for block in sections if block)


def build_system_prompt(base: str, sections: list[str]) -> str:
    """基础文案后按序接非空条件段。"""
    return join_sections([base, *sections])


def inject_user_blocks(msgs: list[dict], sections: list[str]) -> None:
    """各段按序拼到末条用户消息正文前，临时注入不入库；替换为拷贝，不动调用方字典。"""
    text = join_sections(sections)
    if not text:
        return
    for index in range(len(msgs) - 1, -1, -1):
        if msgs[index]["role"] != "user":
            continue
        msgs[index] = {**msgs[index], "content": text + "\n\n" + msgs[index]["content"]}
        return
