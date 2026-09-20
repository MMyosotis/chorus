"""任务服务：人工确认编排与任务图视图。

状态合法性由领域保证，仓储直接翻转；任务图优先进行中流水线，无则取最近已完成。
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from chorus.domain.task import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    TERMINAL_STATUSES,
    Task,
    TaskGraph,
    TaskStatus,
    build_edited_artifacts,
    build_task_graph,
    select_display_pipeline,
    select_pipeline_id,
)
from chorus.domain.log import get_logger
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.memory import MemoryService
from chorus.services.products import load_delivered_products
from chorus.services.session import SessionService

_logger = get_logger("service.task")


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_progress_repo: TaskProgressRepository,
        content_repo: TaskContentRepository,
        session_service: SessionService,
        memory_service: MemoryService,
    ):
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._progress_repo = task_progress_repo
        self._content_repo = content_repo
        self._session = session_service
        self._memory = memory_service

    def confirm(self, task_id: str, selected: Optional[int]) -> dict:
        """确认推进：翻转待确认→完成，候选角色写回选中项（在翻转之后）。"""
        task = self._task_repo.get(task_id)
        self._task_repo.transition(task_id, TaskStatus.FINISHED)
        if task.agent_type == "idea":
            self._set_selected(task_id, task.agent_type, selected)
            self._memory.record_selection(task_id, task.agent_type)
        elif task.agent_type == "finalize":
            self._memory.record_publication(task_id, task.agent_type)
        _logger.info("hil confirm", extra={"task_id": task_id, "selected": selected})
        return {"id": task_id, "status": TaskStatus.FINISHED}

    def edit(self, task_id: str, payload: dict) -> dict:
        """人工编辑产物：按产物类型校验合成，落库。"""
        task = self._task_repo.get(task_id)
        art = self._artifacts_repo.load(task_id)
        artifacts = build_edited_artifacts(art.artifacts, payload)
        self._artifacts_repo.upsert(task_id, task.agent_type, artifacts=artifacts)
        _logger.info("hil edit", extra={"task_id": task_id, "agent_type": task.agent_type})
        return {"id": task_id, "status": task.status}

    def retry(self, task_id: str, feedback: str) -> dict:
        """带反馈重跑本步：翻回待执行并写回反馈。"""
        task = self._task_repo.get(task_id)
        self._task_repo.transition(task_id, TaskStatus.PENDING)
        self._content_repo.set_feedback(task_id, feedback)
        self._memory.record_correction(task_id, task.agent_type, feedback)
        _logger.info("hil retry", extra={"task_id": task_id})
        return {"id": task_id, "status": TaskStatus.PENDING}

    def cancel_pipeline(self, session_id: str) -> dict:
        """放弃整条流水线：批量取消待执行/运行中/待确认/失败任务，无图可弃则幂等返 0。"""
        tasks = self.current_pipeline_tasks(session_id)
        pipeline_id = tasks[0].pipeline_id if tasks else None
        count = self._task_repo.cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES) if pipeline_id else 0
        _logger.info("cancel pipeline", extra={"session_id": session_id, "cancelled": count})
        return {"pipeline_id": pipeline_id, "cancelled": count}

    def get_graph(self, session_id: str) -> TaskGraph:
        """任务图视图：进行中流水线优先，无则取最近已完成。"""
        tasks = self.current_pipeline_tasks(session_id)
        if not tasks:
            return build_task_graph(None, [], {}, {}, {}, False)
        pipeline_id = tasks[0].pipeline_id
        if any(task.status in ACTIVE_STATUSES for task in tasks):
            # 渲染整图含已完成前序，否则成员会随完成逐个消失
            return self._build_graph(pipeline_id, tasks, True)

        # 无进行中：取该会话终态任务，按流水线分组取最近完成
        display = select_display_pipeline([], tasks)
        return self._build_graph(pipeline_id, display, False)

    def count_active(self, session_id: str) -> int:
        """会话内活跃任务数，供入口门禁判定是否进行中。"""
        return self._task_repo.count_by_session_statuses(session_id, ACTIVE_STATUSES)

    def current_pipeline_tasks(self, session_id: str) -> list[Task]:
        """取会话当前流水线的全部任务，活跃流水线优先。"""
        active = self._task_repo.find_by_session_statuses(session_id, ACTIVE_STATUSES)
        terminal = self._task_repo.find_by_session_statuses(session_id, TERMINAL_STATUSES)
        pipeline_id = select_pipeline_id(active, terminal)
        if pipeline_id is None:
            return []
        return self._task_repo.find_by_pipeline(pipeline_id)

    def list_products(self, session_id: str) -> list[dict]:
        """已交付成品列表：本会话全部完成的排版任务，带全文/标题/标识/锚点。"""
        products = load_delivered_products(self._task_repo, self._artifacts_repo, session_id)
        return [dataclasses.asdict(product) for product in products]

    def _set_selected(self, task_id: str, agent_type: str, selected: Optional[int]) -> None:
        """把选中候选写回候选角色产物（子 agent 已先落，必就绪）。"""
        art = self._artifacts_repo.load(task_id)
        idea = dataclasses.replace(art.artifacts, selected=selected)
        self._artifacts_repo.upsert(task_id, agent_type, artifacts=idea)

    def _build_graph(self, pipeline_id: str, tasks: list, active: bool) -> TaskGraph:
        """取本图所需产物/进度/内容，交领域聚合。拓扑序在领域内。"""
        ids = [task.id for task in tasks]
        return build_task_graph(
            pipeline_id,
            tasks,
            self._artifacts_repo.load_many(ids),
            self._progress_repo.load_many(ids),
            self._content_repo.load_many(ids),
            active,
        )
