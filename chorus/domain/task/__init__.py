"""任务图核心领域包：模型、状态机、流水线、角色档案、成品契约。
按业务概念扁平组织，单一概念内聚，不依赖外部层。"""
from __future__ import annotations

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.graph import (
    TaskGraph,
    TaskNodeView,
    build_task_graph,
    dump_task_graph,
)
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
    PostCard,
    PostCardMeta,
    PostImage,
    PostSection,
    PostTable,
    ScriptArtifacts,
    ScriptBlock,
    TaskArtifacts,
)
from chorus.domain.task.progress import (
    TaskProgress,
    dump_progress,
)
from chorus.domain.task.pipeline import (
    StepSpec,
    TaskPlan,
)
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile
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
    "AgentType",
    "IdeaArtifacts",
    "IdeaCandidate",
    "ImageArtifacts",
    "ImageItem",
    "ScriptArtifacts",
    "ScriptBlock",
    "StepSpec",
    "Task",
    "TaskArtifacts",
    "TaskContent",
    "TaskGraph",
    "TaskNodeView",
    "TaskProgress",
    "TaskPlan",
    "TaskStatus",
    "PostCard",
    "PostCardMeta",
    "PostImage",
    "PostSection",
    "PostTable",
    "AgentProfile",
    "AGENT_PROFILES",
    "ACTIVE_STATUSES",
    "CANCELLABLE_STATUSES",
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "select_display_pipeline",
    "topological_order",
    "build_task_graph",
    "dump_progress",
    "dump_task_graph",
]
