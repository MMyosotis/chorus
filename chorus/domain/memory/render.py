"""创作者记忆块渲染：摘要进系统提示词，召回条目进用户回合。"""
from __future__ import annotations

from chorus.domain.memory.models import CreatorMemory, MemoryDigest

_DIGEST_HEADER = "## 创作者档案"
_RECALL_OPEN = "<recalled_memories>"
_RECALL_CLOSE = "</recalled_memories>"


def render_digest_block(digest: MemoryDigest) -> str:
    """摘要为空返空串，否则列条目带平台与类型标记。"""
    if digest.is_empty:
        return ""
    lines = [_DIGEST_HEADER]
    for idx, entry in enumerate(digest.entries, 1):
        platform = f"[{'/'.join(entry.platform)}]" if entry.platform else ""
        mark = "已验证" if entry.kind == "performance" else "参考"
        lines.append(f"{idx}. {entry.description} {platform}（{mark}）")
    return "\n".join(lines)


def render_recall_block(memories: list[CreatorMemory]) -> str:
    """无召回返空串，否则标签包裹逐条列出描述与正文。"""
    if not memories:
        return ""
    lines = [_RECALL_OPEN]
    for idx, memory in enumerate(memories, 1):
        lines.append(f"[{idx}] {memory.description}")
        lines.append(memory.content)
    lines.append(_RECALL_CLOSE)
    return "\n".join(lines)
