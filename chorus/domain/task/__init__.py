# kitty/domain/task/__init__.py
"""任务图核心领域包：模型 + 状态机 + pipeline + profiles + PostCard 成品契约。

按业务概念扁平组织，单一概念内聚：task 图的数据形状、纯状态机规则、pipeline 展开、
角色档案、成品契约同住此包。不 import repos/services/hooks/tools/agents。
"""
from __future__ import annotations

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import (
    AgentType,
    CreationIntent,
    StepSpec,
    Task,
    TaskArtifacts,
    TaskStep,
    TaskStatus,
)
from chorus.domain.task.request import PlanRequest
from chorus.domain.task.post import PostCard, PostImage, PostSection
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile
from chorus.domain.task.pipeline import (
    expand_pipeline,
    parse_output,
    parse_sections,
    render_invoke_message,
    validate_steps,
)
from chorus.domain.task.state_machine import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    can_schedule,
    is_legal_transition,
    is_zombie,
    select_display_pipeline,
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
    "PlanRequest",
    "PostCard",
    "PostImage",
    "PostSection",
    "AgentProfile",
    "AGENT_PROFILES",
    "ACTIVE_STATUSES",
    "CANCELLABLE_STATUSES",
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "can_schedule",
    "is_legal_transition",
    "is_zombie",
    "select_display_pipeline",
    "expand_pipeline",
    "parse_output",
    "parse_sections",
    "render_invoke_message",
    "validate_steps",
]
