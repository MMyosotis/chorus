"""任务图核心领域包：模型、状态机、流水线、角色档案、成品契约。
按业务概念扁平组织，单一概念内聚，不依赖外部层。"""
from __future__ import annotations

from chorus.domain.task.errors import AbandonError, ValidationError
from chorus.domain.task.graph import (
    TaskGraph,
    TaskNodeResponse,
    TaskNodeView,
    TaskProgressResponse,
    build_task_graph,
    build_task_node_response,
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
    ScriptArtifacts,
    TaskArtifacts,
    invoke_text,
    build_edited_artifacts,
)
from chorus.domain.task.progress import (
    TaskProgress,
    dump_progress,
)
from chorus.domain.task.pipeline import (
    StepSpec,
    TaskPlan,
)
from chorus.domain.task.products import (
    CANCELLED_PIPELINE_RECEIPT,
    DeliveredProduct,
    build_delivered_products,
    format_product_list,
    render_delivery_receipt,
    select_delivered_tasks,
)
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile
from chorus.domain.task.state import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    is_legal_transition,
    select_display_pipeline,
    select_pipeline_id,
    topological_order,
)

__all__ = [
    "AbandonError",
    "ValidationError",
    "AgentType",
    "IdeaArtifacts",
    "IdeaCandidate",
    "ImageArtifacts",
    "ImageItem",
    "ScriptArtifacts",
    "StepSpec",
    "Task",
    "TaskArtifacts",
    "TaskContent",
    "TaskGraph",
    "TaskNodeResponse",
    "TaskNodeView",
    "TaskProgress",
    "TaskProgressResponse",
    "TaskPlan",
    "TaskStatus",
    "PostCard",
    "DeliveredProduct",
    "CANCELLED_PIPELINE_RECEIPT",
    "render_delivery_receipt",
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
    "build_task_node_response",
    "dump_progress",
    "dump_task_graph",
    "invoke_text",
    "build_edited_artifacts",
    "build_delivered_products",
    "format_product_list",
    "select_delivered_tasks",
    "select_pipeline_id",
]
