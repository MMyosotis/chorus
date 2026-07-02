"""任务图视图值对象：拓扑序聚合 + 序列化。

围绕单一概念（task graph 投影）的纯数据形状与拼装/序列化规则，不触 repo。
对齐 MessageView：把编排层就地手搓的视图 dict 收为领域模型。
"""
from __future__ import annotations

import dataclasses
from typing import Optional, Union

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.activity import TaskActivity, dump_activity
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
    """任务图节点投影：调度行 + 最新活动 + 产物 + 错误。"""

    id: str
    agent_type: str
    status: str
    updated_at: float
    current_activity: Optional[TaskActivity] = None
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
    activities: dict[str, TaskActivity],
    contents: dict[str, TaskContent],
    active: bool,
) -> TaskGraph:
    """拓扑序聚合任务图：纯函数，不触 repo。"""
    ordered = topological_order(tasks)
    nodes = [TaskNodeView(
        id=t.id,
        agent_type=t.agent_type,
        status=t.status,
        updated_at=t.updated_at,
        current_activity=activities.get(t.id),
        artifacts=arts[t.id].artifacts if t.id in arts else None,
        narrative=arts[t.id].narrative if t.id in arts else None,
        error=contents[t.id].error if t.id in contents else None,
    ) for t in ordered]

    return TaskGraph(pipeline_id=pipeline_id, active=active, nodes=nodes)


def dump_task_graph(g: TaskGraph) -> dict:
    """序列化为前端 wire shape。

    activity 走 dump_activity（多态 payload），artifacts/narrative 走 dataclasses.asdict
    ——与原 service 就地手搓 dict 字节一致。
    """
    return {
        "pipeline_id": g.pipeline_id,
        "active": g.active,
        "tasks": [{
            "id": n.id,
            "agent_type": n.agent_type,
            "status": n.status,
            "updated_at": n.updated_at,
            "current_activity": dump_activity(n.current_activity) if n.current_activity else None,
            "artifacts": dataclasses.asdict(n.artifacts) if n.artifacts else None,
            "narrative": dataclasses.asdict(n.narrative) if n.narrative else None,
            "error": n.error,
        } for n in g.nodes],
    }