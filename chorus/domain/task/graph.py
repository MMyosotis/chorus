"""任务图视图值对象：拓扑序聚合 + 序列化，纯数据形状不碰数据库。"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional, Union, cast

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.progress import TaskProgress, dump_progress
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.task.artifacts import (
    IdeaArtifacts,
    ImageArtifacts,
    PostCard,
    ScriptArtifacts,
    TaskArtifacts,
)
from chorus.domain.task.models import Task, TaskContent
from chorus.domain.task.state import topological_order


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskNodeView:
    """任务图节点投影：调度行 + 运行期进度 + 产物 + 错误。"""

    id: str
    message_id: Optional[str]
    agent_type: str
    status: str
    updated_at: float
    progress: Optional[TaskProgress] = None
    artifacts: Optional[Union[IdeaArtifacts, ScriptArtifacts, ImageArtifacts, PostCard]] = None
    error: Optional[str] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskGraph:
    """任务图视图值对象。"""

    pipeline_id: Optional[str]
    active: bool
    nodes: list[TaskNodeView]


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


def dump_task_graph(graph: TaskGraph) -> dict:
    """序列化为前端传输结构。"""
    return {
        "pipeline_id": graph.pipeline_id,
        "active": graph.active,
        "tasks": [{
            "id": node.id,
            "message_id": node.message_id,
            "agent_type": node.agent_type,
            "status": node.status,
            "updated_at": node.updated_at,
            "progress": _dump_progress_with_line(node.progress, node.agent_type) if node.progress else None,
            "artifacts": dataclasses.asdict(cast(Any, node.artifacts)) if node.artifacts else None,
            "error": node.error,
        } for node in graph.nodes],
    }


def _dump_progress_with_line(progress: TaskProgress, agent_type: str) -> dict:
    """序列化进度快照，并按角色补活动台词。"""
    data = dump_progress(progress)
    profile = AGENT_PROFILES.get(agent_type)
    if profile:
        data["activity_line"] = profile.activity_line(progress.activity_kind)
    return data
