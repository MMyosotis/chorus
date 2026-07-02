"""任务图核心领域包：模型、状态机、流水线、角色档案、成品契约。

按业务概念扁平组织，单一概念内聚，不依赖外部层。
"""
from __future__ import annotations

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import (
    AgentType,
    CreationIntent,
    IdeaArtifacts,
    IdeaCandidate,
    ImageArtifacts,
    ImageItem,
    Narrative,
    PostCard,
    PostImage,
    PostSection,
    ScriptArtifacts,
    ScriptBlock,
    StepSpec,
    Task,
    TaskActivity,
    TaskArtifacts,
    TaskStatus,
)
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile
from chorus.domain.task.pipeline import (
    expand_pipeline,
    parse_output,
    parse_sections,
    render_invoke_message,
    validate_steps,
)
from chorus.domain.task.state import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    can_schedule,
    is_legal_transition,
    is_zombie,
    select_display_pipeline,
    topological_order,
)

__all__ = [
    "ValidationError",
    "AgentType",
    "CreationIntent",
    "IdeaArtifacts",
    "IdeaCandidate",
    "ImageArtifacts",
    "ImageItem",
    "Narrative",
    "ScriptArtifacts",
    "ScriptBlock",
    "StepSpec",
    "Task",
    "TaskActivity",
    "TaskArtifacts",
    "TaskStatus",
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
    "topological_order",
    "expand_pipeline",
    "parse_output",
    "parse_sections",
    "render_invoke_message",
    "validate_steps",
]
