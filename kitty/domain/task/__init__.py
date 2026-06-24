# kitty/domain/task/__init__.py
"""任务图核心领域包：模型 + 状态机 + pipeline + profiles + PostCard 成品契约。

按业务概念扁平组织，单一概念内聚：task 图的数据形状、纯状态机规则、pipeline 展开、
角色档案、成品契约同住此包。不 import repos/services/hooks/tools/agents。
"""
from __future__ import annotations

from kitty.domain.task.errors import ValidationError
from kitty.domain.task.models import (
    AgentType,
    CreationIntent,
    StepSpec,
    Task,
    TaskArtifacts,
    TaskStep,
    TaskStatus,
)

__all__ = [
    "ValidationError",
    "AgentType",
    "CreationIntent",
    "StepSpec",
    "Task",
    "TaskArtifacts",
    "TaskStep",
    "TaskStatus",
]
