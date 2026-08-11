"""创作者记忆可见性纯函数。"""
from __future__ import annotations

from chorus.domain.memory.models import CreatorMemory, MemoryDigestEntry


def visible_to_agent(memory: CreatorMemory, agent_type: str) -> bool:
    """编排者全可见，其余角色看可见性列表为空或含自身。"""
    if agent_type == "supervisor":
        return True
    return not memory.visible_to or agent_type in memory.visible_to


def memories_to_digest_entries(memories: list[CreatorMemory], agent_type: str) -> list[MemoryDigestEntry]:
    """按角色可见性过滤记忆并投影为摘要条目。"""
    return [
        MemoryDigestEntry(
            id=memory.id,
            description=memory.description,
            platform=list(memory.platform),
            kind=memory.kind,
        )
        for memory in memories
        if visible_to_agent(memory, agent_type)
    ]
