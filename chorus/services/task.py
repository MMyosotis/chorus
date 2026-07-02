"""任务服务：人工确认编排与任务图视图。

编排层取数据调领域再存数据。状态翻转合法性由领域保证，仓储只做原子翻转；
确认与重跑先查存在再翻转，翻转失败抛冲突错由路由转 409。任务图优先展示进行中流水线，
无则取最近已完成。
"""
from __future__ import annotations

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
from chorus.services.session import SessionService

_TASK_ACTIVITY_ADAPTER = TypeAdapter(TaskActivity)


def _dump_activity(a: TaskActivity) -> dict:
    """序列化活动，用类型适配器替代模型导出。"""
    return _TASK_ACTIVITY_ADAPTER.dump_python(a)


class ConflictError(Exception):
    """状态冲突或前置条件不满足。"""


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_activities_repo: TaskActivitiesRepository,
        session_service: SessionService,
    ):
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._activities_repo = task_activities_repo
        self._session = session_service

    def confirm(self, task_id: str, selected: Optional[int]) -> dict:
        """确认推进：翻转待确认态为完成。选题角色校验选中项并写回产物。"""
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
        """带反馈重跑本步：写回反馈并翻转回待执行。"""
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
        """放弃整条流水线：找进行中流水线，事务内批量取消非终态任务。"""
        pipeline_id = self._active_pipeline_id(session_id)
        if pipeline_id is None:
            raise ConflictError("该会话无进行中的创作任务")
        n = self._task_repo.cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES)
        return {"pipeline_id": pipeline_id, "cancelled": n}

    def get_graph(self, session_id: str) -> dict:
        """任务图视图：进行中流水线优先，无则取最近已完成。"""
        active_tasks = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        if active_tasks:
            # 渲染整图含已完成前序，否则成员会随完成逐个消失
            pipeline_id = active_tasks[0].pipeline_id
            all_tasks = self._task_repo.find_by_pipeline(pipeline_id)
            return self._graph_dict(pipeline_id, all_tasks, True)
        # 无进行中：取该会话终态任务，按流水线分组取最近完成
        terminal = self._task_repo.find_by_session_statuses(session_id, TERMINAL_STATUSES)
        if not terminal:
            return {"pipeline_id": None, "active": False, "tasks": []}
        # 取最近更新的流水线
        latest = max(terminal, key=lambda t: t.updated_at)
        same_pipeline = [t for t in terminal if t.pipeline_id == latest.pipeline_id]
        display = select_display_pipeline([], same_pipeline)
        return self._graph_dict(latest.pipeline_id, display, False)

    def get_activities(self, task_id: str, *, limit: int = 50) -> list[dict]:
        """返回该任务的用户态活动，按发生顺序。"""
        if self._task_repo.get(task_id) is None:
            raise KeyError(task_id)
        limit = max(1, min(100, limit))
        rows = self._activities_repo.list_by_task(task_id, limit=limit)
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
                    "finished_at": t.finished_at,
                    "current_activity": _dump_activity(latest[t.id]) if t.id in latest else None,
                    "artifacts": (arts[t.id].artifacts if t.id in arts else None),
                    "narrative": (arts[t.id].narrative if t.id in arts else None),
                    "error": t.error,
                }
                for t in ordered
            ],
        }
