"""提示词装配机制：条件成段、系统段拼接、条件段注入末条用户消息。

各位置具体拼了哪些段，见 prompt/subagent.py 与 prompt/supervisor.py。
"""
from __future__ import annotations

from typing import Optional


def section(title: str, body: Optional[str], inline: bool = False) -> str:
    """有正文则标题接正文成段，无正文返空串。"""
    if not body:
        return ""
    separator = "" if inline else "\n"
    return f"{title}{separator}{body}"


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
