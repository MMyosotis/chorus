"""任务图视图值对象：拓扑序聚合 + 序列化，纯数据形状不碰数据库。"""
from __future__ import annotations

import re
from functools import singledispatch
from typing import Any, Optional, Union

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

_OUTPUT_ORDER: tuple[AgentType, ...] = (AgentType.IDEA, AgentType.SCRIPT, AgentType.IMAGE, AgentType.FINALIZE)
_H2_RE = re.compile(r"(?m)^##\s")
_EMPTY_OUTPUT_FIELDS: dict[AgentType, dict] = {
    AgentType.IDEA: {"title": ""},
    AgentType.SCRIPT: {"char_count": 0, "block_count": 0},
    AgentType.IMAGE: {"image_count": 0},
    AgentType.FINALIZE: {"title": ""},
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

    @classmethod
    def from_progress(cls, progress: TaskProgress, agent_type: AgentType) -> "TaskProgressResponse":
        """从运行期进度构造传输模型，并补充活动台词。"""
        profile = AGENT_PROFILES[agent_type]
        return cls(
            task_id=progress.task_id,
            composing_chars=progress.composing_chars,
            composing_units=progress.composing_units,
            composing_label=progress.composing_label,
            last_signal=progress.last_signal,
            aside=progress.aside,
            activity_kind=progress.activity_kind,
            activity_detail=progress.activity_detail,
            activity_line=profile.activity_line(progress.activity_kind),
        )


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

    @classmethod
    def from_view(cls, node: TaskNodeView) -> "TaskNodeResponse":
        """从图节点构造前端传输模型。"""
        return cls(
            id=node.id,
            message_id=node.message_id,
            agent_type=node.agent_type,
            status=node.status,
            updated_at=node.updated_at,
            progress=TaskProgressResponse.from_progress(node.progress, node.agent_type) if node.progress else None,
            artifacts=node.artifacts,
            error=node.error,
        )


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
        "tasks": [TaskNodeResponse.from_view(node).model_dump(mode="json") for node in graph.nodes],
        "outputs": _output_rows(graph),
    }


@singledispatch
def _artifact_fields(artifacts: Any) -> dict:
    """按产物类型汇总产出段字段。"""
    raise NotImplementedError


@_artifact_fields.register
def _idea_fields(artifacts: IdeaArtifacts) -> dict:
    candidate = artifacts.selected_candidate()
    return {"title": candidate.title if candidate else ""}


@_artifact_fields.register
def _script_fields(artifacts: ScriptArtifacts) -> dict:
    return {
        "char_count": len(artifacts.markdown),
        "block_count": len(_H2_RE.findall(artifacts.markdown)),
    }


@_artifact_fields.register
def _image_fields(artifacts: ImageArtifacts) -> dict:
    return {"image_count": len(artifacts.images)}


@_artifact_fields.register
def _postcard_fields(artifacts: PostCard) -> dict:
    return {"title": artifacts.meta.title}


def _first_finished_by_agent(graph: TaskGraph) -> dict[AgentType, TaskNodeView]:
    """各角色首条完成任务，保持图内出现顺序。"""
    first_finished: dict[AgentType, TaskNodeView] = {}
    for node in graph.nodes:
        if node.status != TaskStatus.FINISHED:
            continue
        first_finished.setdefault(node.agent_type, node)
    return first_finished


def _output_rows(graph: TaskGraph) -> list[dict]:
    """创作产出段成品行：各角色首条完成任务按流水线顺序投影。"""
    first_finished = _first_finished_by_agent(graph)
    rows = []
    for agent_type in _OUTPUT_ORDER:
        node = first_finished.get(agent_type)
        if node is None:
            continue
        fields = _artifact_fields(node.artifacts) if node.artifacts is not None else _EMPTY_OUTPUT_FIELDS[agent_type]
        rows.append({"kind": agent_type.value, "task_id": node.id, **fields})
    return rows
