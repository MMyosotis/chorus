"""任务图视图值对象：拓扑序聚合 + 序列化，纯数据形状不碰数据库。"""
from __future__ import annotations

import dataclasses
from typing import Optional, Union

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.progress import TaskProgress, dump_progress
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.task.artifacts import (
    IdeaArtifacts,
    ImageArtifacts,
    Narrative,
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
    agent_type: str
    status: str
    updated_at: float
    progress: Optional[TaskProgress] = None
    artifacts: Optional[Union[IdeaArtifacts, ScriptArtifacts, ImageArtifacts, PostCard]] = None
    narrative: Optional[Narrative] = None
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
    nodes = [TaskNodeView(
        id=task.id,
        agent_type=task.agent_type,
        status=task.status,
        updated_at=task.updated_at,
        progress=progress.get(task.id),
        artifacts=arts[task.id].artifacts if task.id in arts else None,
        narrative=arts[task.id].narrative if task.id in arts else None,
        error=contents[task.id].error if task.id in contents else None,
    ) for task in ordered]

    return TaskGraph(pipeline_id=pipeline_id, active=active, nodes=nodes)


def dump_task_graph(graph: TaskGraph) -> dict:
    """序列化为前端传输结构。"""
    return {
        "pipeline_id": graph.pipeline_id,
        "active": graph.active,
        "tasks": [{
            "id": node.id,
            "agent_type": node.agent_type,
            "status": node.status,
            "updated_at": node.updated_at,
            "progress": _dump_progress_with_line(node) if node.progress else None,
            "artifacts": dataclasses.asdict(node.artifacts) if node.artifacts else None,
            "narrative": dataclasses.asdict(node.narrative) if node.narrative else None,
            "error": node.error,
        } for node in graph.nodes],
    }


def _dump_progress_with_line(node: TaskNodeView) -> dict:
    """序列化进度快照，并按角色补活动台词。"""
    data = dump_progress(node.progress)
    profile = AGENT_PROFILES.get(node.agent_type)
    if profile:
        data["activity_line"] = profile.activity_line(node.progress.activity_kind)
    return data