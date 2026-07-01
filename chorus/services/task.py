# kitty/services/task.py
"""TaskService：HIL（confirm/retry/cancel）编排 + get_graph 任务图视图。

编排层：取数据→调 domain→存数据。CAS 合法性由 domain LEGAL_TRANSITIONS 保证（service
结构性只做一条合法翻转）；repo cas_update 仅原子原语。confirm/retry 先查存在性再 CAS，
rowcount=0 抛 ConflictError（route 转 409）。get_graph 选 active pipeline，无 active
选最近 finished（cancelled 不算）。
"""
from __future__ import annotations

import dataclasses
import time
from typing import Any, Optional

from pydantic import TypeAdapter

from chorus.domain.task import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    TERMINAL_STATUSES,
    TaskActivity,
    TaskStatus,
    select_display_pipeline,
    topological_order,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_steps import TaskStepsRepository
from chorus.services.session import SessionService

_TASK_ACTIVITY_ADAPTER = TypeAdapter(TaskActivity)


def _dump_activity(a: TaskActivity) -> dict:
    """pydantic dataclass 无 model_dump，用 TypeAdapter 序列化（不用 dataclasses.asdict）。"""
    return _TASK_ACTIVITY_ADAPTER.dump_python(a)


class ConflictError(Exception):
    """CAS 冲突（状态已漂移）或前置条件不满足（如 idea 缺 selected）。"""


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_steps_repo: TaskStepsRepository,
        task_activities_repo: TaskActivitiesRepository,
        session_service: SessionService,
    ):
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._steps_repo = task_steps_repo
        self._activities_repo = task_activities_repo
        self._session = session_service

    def confirm(self, task_id: str, selected: Optional[int]) -> dict:
        """确认推进：CAS awaiting_confirm→finished。idea 校验 selected 并写 artifacts.selected。"""
        task = self._task_repo.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != TaskStatus.AWAITING_CONFIRM.value:
            raise ConflictError(f"task 状态 {task.status} 不可确认")
        if task.agent_type == "idea":
            if selected is None:
                raise ConflictError("idea 步骤需提供 selected 候选索引")
            self._set_selected(task_id, selected)
        ok = self._task_repo.cas_update(
            task_id, TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FINISHED.value,
            finished_at=time.time(),
        )
        if not ok:
            raise ConflictError("CAS 失败（状态已漂移）")
        return {"id": task_id, "status": TaskStatus.FINISHED.value}

    def retry(self, task_id: str, feedback: dict) -> dict:
        """带反馈重跑本步：写 feedback + CAS awaiting_confirm→pending（或 failed→pending）。"""
        task = self._task_repo.get(task_id)
        if task is None:
            raise KeyError(task_id)
        from_status = task.status
        if from_status not in (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FAILED.value):
            raise ConflictError(f"task 状态 {from_status} 不可重跑")
        ok = self._task_repo.cas_update(
            task_id, from_status, TaskStatus.PENDING.value, feedback=feedback,
        )
        if not ok:
            raise ConflictError("CAS 失败（状态已漂移）")
        return {"id": task_id, "status": TaskStatus.PENDING.value}

    def cancel_pipeline(self, session_id: str) -> dict:
        """放弃整条 pipeline：找该 session active pipeline_id，事务批量 CAS 非终态→cancelled。"""
        pipeline_id = self._active_pipeline_id(session_id)
        if pipeline_id is None:
            raise ConflictError("该会话无进行中的创作任务")
        n = self._task_repo.cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES)
        return {"pipeline_id": pipeline_id, "cancelled": n}

    def get_graph(self, session_id: str) -> dict:
        """任务图视图：active pipeline 优先，无 active 选最近 finished。"""
        active_tasks = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        if active_tasks:
            # 渲染整图（含已 finished 的前序 task），否则团队成员会随完成逐个消失
            pipeline_id = active_tasks[0].pipeline_id
            all_tasks = self._task_repo.find_by_pipeline(pipeline_id)
            return self._graph_dict(pipeline_id, all_tasks, True)
        # 无 active：找该 session 所有终态 task，按 pipeline 分组取最近 finished
        terminal = self._task_repo.find_by_session_statuses(session_id, TERMINAL_STATUSES)
        if not terminal:
            return {"pipeline_id": None, "active": False, "tasks": []}
        # 选最近 updated 的 pipeline
        latest = max(terminal, key=lambda t: t.updated_at)
        same_pipeline = [t for t in terminal if t.pipeline_id == latest.pipeline_id]
        display = select_display_pipeline([], same_pipeline)  # active 空，返 finished 子集
        return self._graph_dict(latest.pipeline_id, display, False)

    def get_steps(self, task_id: str) -> list[dict]:
        """该 task 的 ReAct 过程（按 iteration 升序），供角色详情页。

        已被 get_activities（用户态活动流）部分取代，保留供 ReAct 开发者视图。
        """
        if self._task_repo.get(task_id) is None:
            raise KeyError(task_id)
        return [dataclasses.asdict(s) for s in self._steps_repo.list_by_task(task_id)]

    def get_activities(
        self, task_id: str, *, limit: int = 50, after_seq: Optional[int] = None,
    ) -> list[dict]:
        """该 task 的用户态活动（按 seq 升序），供 Dock 活动流。"""
        if self._task_repo.get(task_id) is None:
            raise KeyError(task_id)
        limit = max(1, min(100, limit))
        rows = self._activities_repo.list_by_task(task_id, limit=limit, after_seq=after_seq)
        return [_dump_activity(a) for a in rows]

    def _active_pipeline_id(self, session_id: str) -> Optional[str]:
        active = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        return active[0].pipeline_id if active else None

    def _set_selected(self, task_id: str, selected: int) -> None:
        art = self._artifacts_repo.load(task_id)
        artifacts = art.artifacts if art else {}
        artifacts = dict(artifacts)
        artifacts["selected"] = selected
        self._artifacts_repo.upsert(
            task_id, artifacts=artifacts,
            narrative=art.narrative if art else None,
        )

    def _graph_dict(self, pipeline_id: str, tasks: list, active: bool) -> dict:
        ordered = topological_order(tasks)
        arts = self._artifacts_repo.load_many([t.id for t in ordered])
        latest = self._activities_repo.latest_by_tasks([t.id for t in ordered])
        return {
            "pipeline_id": pipeline_id,
            "active": active,
            "tasks": [
                {
                    "id": t.id, "agent_type": t.agent_type, "status": t.status,
                    "updated_at": t.updated_at, "started_at": t.started_at,
                    "finished_at": t.finished_at, "metadata": t.metadata,
                    "current_activity": _dump_activity(latest[t.id]) if t.id in latest else None,
                    "artifacts": (arts[t.id].artifacts if t.id in arts else None),
                    "narrative": (arts[t.id].narrative if t.id in arts else None),
                    "error": t.error,
                }
                for t in ordered
            ],
        }
