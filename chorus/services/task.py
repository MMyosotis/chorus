"""任务服务：人工确认编排与任务图视图。

编排层取数据调领域再存数据。状态翻转合法性由领域保证，仓储只做原子翻转；
确认与重跑先查存在再翻转，翻转失败抛冲突错由路由转 409。任务图优先展示进行中流水线，
无则取最近已完成。
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from chorus.domain.task import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    TERMINAL_STATUSES,
    TaskStatus,
    dump_activity,
    select_display_pipeline,
    topological_order,
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
        """确认推进：翻转待确认→完成，idea 角色写回选中候选。

        副作用（写 selected）在翻转之后，对齐 subagent _finalize。task_id 来自
        get_graph 存活行，单用户 sequential 下状态不会漂移，故不设 CAS 守卫。
        """
        task = self._task_repo.get(task_id)
        self._task_repo.transition(task_id, TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FINISHED.value)
        if task.agent_type == "idea":
            self._set_selected(task_id, task.agent_type, selected)
        return {"id": task_id, "status": TaskStatus.FINISHED.value}

    def retry(self, task_id: str, feedback: dict) -> dict:
        """带反馈重跑本步：CAS 翻转回待执行并写回反馈（允许从待确认或失败态）。

        起点态 awaiting_confirm/failed 是 worker 已停的稳态，无并发写方，故 CAS 与
        feedback 写入不包事务（单条 UPDATE/UPSERT 各自原子）。CAS 依次尝试两态，
        任一命中即写反馈返回；都失败说明状态已漂移或任务不存在。
        """
        for from_status in (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FAILED.value):
            if not self._task_repo.transition(task_id, from_status, TaskStatus.PENDING.value):
                continue
            self._content_repo.set_feedback(task_id, feedback)
            return {"id": task_id, "status": TaskStatus.PENDING.value}
        raise ConflictError("CAS 失败（状态已漂移）")

    def cancel_pipeline(self, session_id: str) -> dict:
        """放弃整条流水线：批量取消进行中流水线的非终态任务。无 active 则幂等返 0。"""
        pipeline_id = self._active_pipeline_id(session_id)
        n = self._task_repo.cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES) if pipeline_id else 0
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
        limit = max(1, min(100, limit))
        rows = self._activities_repo.list_by_task(task_id, limit=limit)
        return [dump_activity(a) for a in rows]

    def _active_pipeline_id(self, session_id: str) -> Optional[str]:
        active = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        return active[0].pipeline_id if active else None

    def _set_selected(self, task_id: str, agent_type: str, selected: Optional[int]) -> None:
        """把选中候选写回 idea 产物（产物由 subagent _finalize 事务内原子写入，必就绪）。"""
        art = self._artifacts_repo.load(task_id)
        idea = dataclasses.replace(art.artifacts, selected=selected)
        self._artifacts_repo.upsert(
            task_id, agent_type, artifacts=idea, narrative=art.narrative,
        )

    def _graph_dict(self, pipeline_id: str, tasks: list, active: bool) -> dict:
        ordered = topological_order(tasks)
        ids = [t.id for t in ordered]
        arts = self._artifacts_repo.load_many(ids)
        latest = self._activities_repo.latest_by_tasks(ids)
        contents = self._content_repo.load_many(ids)
        return {
            "pipeline_id": pipeline_id,
            "active": active,
            "tasks": [
                {
                    "id": t.id, "agent_type": t.agent_type, "status": t.status,
                    "updated_at": t.updated_at,
                    "current_activity": dump_activity(latest[t.id]) if t.id in latest else None,
                    "artifacts": (
                        dataclasses.asdict(arts[t.id].artifacts) if t.id in arts else None
                    ),
                    "narrative": (
                        dataclasses.asdict(arts[t.id].narrative) if t.id in arts else None
                    ),
                    "error": contents[t.id].error,
                }
                for t in ordered
            ],
        }
