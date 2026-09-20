"""任务图视图值对象：拓扑序聚合 + 序列化，纯数据形状不碰数据库。"""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.progress import TaskProgress
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.task.artifacts import (
    IdeaArtifacts,
    ImageArtifacts,
    PostCard,
    ScriptArtifacts,
    TaskArtifacts,
)
from chorus.domain.task.models import AgentType, Task, TaskContent, TaskStatus
from chorus.domain.task.state import topological_order

_STAGE_STATUS_PRIORITY: dict[TaskStatus, int] = {
    TaskStatus.FAILED: 0,
    TaskStatus.AWAITING_CONFIRM: 1,
    TaskStatus.RUNNING: 2,
}
_STAGE_AGENT_PRIORITY: dict[AgentType, int] = {
    agent_type: index
    for index, agent_type in enumerate((
        AgentType.IDEA,
        AgentType.SCRIPT,
        AgentType.IMAGE,
        AgentType.FINALIZE,
    ))
}


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskNodeView:
    """任务图节点投影：调度行 + 运行期进度 + 产物 + 错误。"""

    id: str
    message_id: Optional[str]
    agent_type: AgentType
    status: TaskStatus
    updated_at: float
    progress: Optional[TaskProgress] = None
    artifacts: Optional[Union[IdeaArtifacts, ScriptArtifacts, ImageArtifacts, PostCard]] = None
    error: Optional[str] = None

    def is_stage_active(self) -> bool:
        return self.status in _STAGE_STATUS_PRIORITY

    def stage_sort_key(self) -> tuple[int, int, str, str]:
        return (
            _STAGE_STATUS_PRIORITY[self.status],
            _STAGE_AGENT_PRIORITY[self.agent_type],
            self.agent_type, self.id,
        )


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskGraph:
    """任务图视图值对象。"""

    pipeline_id: Optional[str]
    active: bool
    nodes: list[TaskNodeView]


class TaskProgressResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    composing_chars: int = 0
    composing_units: int = 0
    composing_label: str = ""
    last_signal: str = ""
    aside: str = ""
    activity_kind: str = ""
    activity_detail: str = ""
    activity_line: Optional[str] = Field(default=None, exclude_if=lambda value: value is None)


class TaskNodeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    message_id: Optional[str]
    agent_type: AgentType
    status: TaskStatus
    updated_at: float
    progress: Optional[TaskProgressResponse] = None
    artifacts: Optional[Union[IdeaArtifacts, ScriptArtifacts, ImageArtifacts, PostCard]] = None
    error: Optional[str] = None


def build_task_graph(
    pipeline_id: Optional[str],
    tasks: list[Task],
    arts: dict[str, TaskArtifacts],
    progress: dict[str, TaskProgress],
    contents: dict[str, TaskContent],
    active: bool,
) -> TaskGraph:
    """拓扑序聚合任务图：纯函数，不碰数据库。"""
    ordered = topological_order(tasks)
    nodes = []
    for task in ordered:
        content = contents.get(task.id)
        art = arts.get(task.id)
        artifacts = art.artifacts if art else None
        nodes.append(TaskNodeView(
            id=task.id,
            message_id=task.message_id,
            agent_type=task.agent_type,
            status=task.status,
            updated_at=task.updated_at,
            progress=progress.get(task.id),
            artifacts=artifacts,
            error=content.error if content else None,
        ))

    return TaskGraph(pipeline_id=pipeline_id, active=active, nodes=nodes)


def build_task_node_response(node: TaskNodeView) -> TaskNodeResponse:
    """把任务节点转换为前端传输模型。"""
    progress = _build_progress_response(node.progress, node.agent_type) if node.progress else None
    return TaskNodeResponse(
        id=node.id,
        message_id=node.message_id,
        agent_type=node.agent_type,
        status=node.status,
        updated_at=node.updated_at,
        progress=progress,
        artifacts=node.artifacts,
        error=node.error,
    )


def dump_task_graph(graph: TaskGraph) -> dict:
    """序列化为前端传输结构。"""
    return {
        "pipeline_id": graph.pipeline_id,
        "active": graph.active,
        "tasks": [build_task_node_response(node).model_dump(mode="json") for node in graph.nodes],
    }


def _build_progress_response(
    progress: TaskProgress,
    agent_type: AgentType,
) -> TaskProgressResponse:
    """把任务进度转换为传输模型，并补充活动台词。"""
    profile = AGENT_PROFILES[agent_type]
    activity_line = profile.activity_line(progress.activity_kind)
    return TaskProgressResponse(
        task_id=progress.task_id,
        composing_chars=progress.composing_chars,
        composing_units=progress.composing_units,
        composing_label=progress.composing_label,
        last_signal=progress.last_signal,
        aside=progress.aside,
        activity_kind=progress.activity_kind,
        activity_detail=progress.activity_detail,
        activity_line=activity_line,
    )
