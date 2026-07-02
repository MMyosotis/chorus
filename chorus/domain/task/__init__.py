"""任务图核心领域包：模型、状态机、流水线、角色档案、成品契约。

按业务概念扁平组织，单一概念内聚，不依赖外部层。
"""
from __future__ import annotations

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import (
    AgentType,
    Task,
    TaskContent,
    TaskStatus,
)
from chorus.domain.task.artifacts import (
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
    TaskArtifacts,
)
from chorus.domain.task.activity import (
    ActivityDraft,
    FailedPayload,
    ImageProgressPayload,
    PAYLOAD_TYPES,
    SearchResultsPayload,
    TaskActivity,
    build_payload,
    dump_activity,
)
from chorus.domain.task.pipeline import (
    CreationIntent,
    StepSpec,
    validate_steps,
)
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile, parse_sections
from chorus.domain.task.state import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    is_legal_transition,
    select_display_pipeline,
    topological_order,
)

__all__ = [
    "ValidationError",
    "ActivityDraft",
    "AgentType",
    "CreationIntent",
    "FailedPayload",
    "IdeaArtifacts",
    "IdeaCandidate",
    "ImageArtifacts",
    "ImageItem",
    "ImageProgressPayload",
    "Narrative",
    "ScriptArtifacts",
    "ScriptBlock",
    "SearchResultsPayload",
    "StepSpec",
    "Task",
    "TaskActivity",
    "TaskArtifacts",
    "TaskContent",
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
    "is_legal_transition",
    "select_display_pipeline",
    "topological_order",
    "parse_sections",
    "validate_steps",
    "PAYLOAD_TYPES",
    "build_payload",
    "dump_activity",
]
