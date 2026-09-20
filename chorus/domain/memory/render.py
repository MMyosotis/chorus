"""创作者记忆正文渲染：最终标签由提示词装配侧添加。"""
from __future__ import annotations

from chorus.domain.memory.models import CreatorMemory, MemoryDigest


def render_digest(digest: MemoryDigest) -> str:
    """摘要为空返空串，否则列条目带平台与类型标记。"""
    if digest.is_empty:
        return ""
    lines = []
    for idx, entry in enumerate(digest.entries, 1):
        platform = f"[{'/'.join(entry.platform)}]" if entry.platform else ""
        mark = "已验证" if entry.kind == "performance" else "参考"
        lines.append(f"{idx}. {entry.description} {platform}（{mark}）")
    return "\n".join(lines)


def render_recall(memories: list[CreatorMemory]) -> str:
    """无召回返空串，否则逐条列出描述与正文。"""
    if not memories:
        return ""
    lines = []
    for idx, memory in enumerate(memories, 1):
        lines.append(f"[{idx}] {memory.description}")
        lines.append(memory.content)
    return "\n".join(lines)
