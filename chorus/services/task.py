"""任务服务：人工确认编排与任务图视图。

状态合法性由领域保证，仓储原子翻转，翻转失败抛冲突错；任务图优先进行中流水线，无则取最近已完成。
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from chorus.domain.task import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    TERMINAL_STATUSES,
    TaskGraph,
    TaskStatus,
    build_task_graph,
    dump_activity,
    select_display_pipeline,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.session import SessionService


class ConflictError(Exception):
    """状态冲突或前置条件不满足。"""


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_activities_repo: TaskActivitiesRepository,
        content_repo: TaskContentRepository,
        session_service: SessionService,
        conn,
    ):
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._activities_repo = task_activities_repo
        self._content_repo = content_repo
        self._session = session_service
        self._conn = conn

    def confirm(self, task_id: str, selected: Optional[int]) -> dict:
        """确认推进：翻转待确认→完成，候选角色写回选中项（在翻转之后）。"""
        task = self._task_repo.get(task_id)
        self._task_repo.transition(task_id, TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FINISHED.value)
        if task.agent_type == "idea":
            self._set_selected(task_id, task.agent_type, selected)
        return {"id": task_id, "status": TaskStatus.FINISHED.value}

    def retry(self, task_id: str, feedback: dict) -> dict:
        """带反馈重跑本步：CAS 翻转回待执行并写回反馈，允许从待确认或失败态。"""
        for from_status in (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FAILED.value):
            if not self._task_repo.transition(task_id, from_status, TaskStatus.PENDING.value):
                continue
            self._content_repo.set_feedback(task_id, feedback)
            return {"id": task_id, "status": TaskStatus.PENDING.value}
        raise ConflictError("CAS 失败（状态已漂移）")

    def cancel_pipeline(self, session_id: str) -> dict:
        """放弃整条流水线：批量取消进行中流水线的非终态任务。无进行中则幂等返 0。"""
        pipeline_id = self._active_pipeline_id(session_id)
        count = self._task_repo.cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES) if pipeline_id else 0
        return {"pipeline_id": pipeline_id, "cancelled": count}

    def get_graph(self, session_id: str) -> TaskGraph:
        """任务图视图：进行中流水线优先，无则取最近已完成。"""
        active_tasks = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        if active_tasks:
            # 渲染整图含已完成前序，否则成员会随完成逐个消失
            pipeline_id = active_tasks[0].pipeline_id
            all_tasks = self._task_repo.find_by_pipeline(pipeline_id)
            return self._build_graph(pipeline_id, all_tasks, True)

        # 无进行中：取该会话终态任务，按流水线分组取最近完成
        terminal = self._task_repo.find_by_session_statuses(session_id, TERMINAL_STATUSES)
        if not terminal:
            return build_task_graph(None, [], {}, {}, {}, False)

        # 取最近更新的流水线
        latest = max(terminal, key=lambda task: task.updated_at)
        same_pipeline = [task for task in terminal if task.pipeline_id == latest.pipeline_id]
        display = select_display_pipeline([], same_pipeline)
        return self._build_graph(latest.pipeline_id, display, False)

    def get_activities(self, task_id: str, *, limit: int = 50) -> list[dict]:
        """返回该任务的用户态活动，按发生顺序。"""
        limit = max(1, min(100, limit))
        rows = self._activities_repo.list_by_task(task_id, limit=limit)
        return [dump_activity(activity) for activity in rows]

    def _active_pipeline_id(self, session_id: str) -> Optional[str]:
        active = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        return active[0].pipeline_id if active else None

    def _set_selected(self, task_id: str, agent_type: str, selected: Optional[int]) -> None:
        """把选中候选写回候选角色产物（子 agent 事务内原子写入，必就绪）。"""
        art = self._artifacts_repo.load(task_id)
        idea = dataclasses.replace(art.artifacts, selected=selected)
        self._artifacts_repo.upsert(
            task_id, agent_type, artifacts=idea, narrative=art.narrative,
        )

    def _build_graph(self, pipeline_id: str, tasks: list, active: bool) -> TaskGraph:
        """取本图所需产物/活动/内容，交领域聚合。拓扑序在领域内。"""
        ids = [task.id for task in tasks]
        return build_task_graph(
            pipeline_id,
            tasks,
            self._artifacts_repo.load_many(ids),
            self._activities_repo.latest_by_tasks(ids),
            self._content_repo.load_many(ids),
            active,
        )
