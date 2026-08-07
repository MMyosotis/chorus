"""创作者记忆可见性纯函数。"""
from __future__ import annotations

from chorus.domain.memory.models import CreatorMemory


def visible_to_agent(memory: CreatorMemory, agent_type: str) -> bool:
    """编排者全可见，其余角色看可见性列表为空或含自身。"""
    if agent_type == "supervisor":
        return True
    return not memory.visible_to or agent_type in memory.visible_to
