"""任务租约守卫:终态写入前校验归属,防陈旧线程残留孤儿产物。"""
from __future__ import annotations

from typing import Optional

from chorus.domain.log import get_logger
from chorus.domain.task import TaskStatus
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository

_logger = get_logger("lease")


class LeaseGuard:
    """任务终态写入守卫:翻转前校验租约,归属漂移即丢弃写入。"""

    def __init__(
        self,
        task_repo: TaskRepository,
        artifacts_repo: TaskArtifactsRepository,
        content_repo: TaskContentRepository,
        progress_repo: TaskProgressRepository,
    ):
        self._task_repo = task_repo
        self._artifacts_repo = artifacts_repo
        self._content_repo = content_repo
        self._progress_repo = progress_repo

    def valid(self, task_id: str, owner_id: Optional[float]) -> bool:
        latest = self._task_repo.get(task_id)
        return latest is not None and latest.status == TaskStatus.RUNNING and latest.owner_id == owner_id

    def finalize(self, task, artifacts, owner_id: Optional[float]) -> None:
        """先校验租约再翻转待复核并落产物,漂移即放弃。"""
        if not self.valid(task.id, owner_id):
            _logger.warning("lease invalid, drop finalize", extra={"task_id": task.id})
            return
        self._task_repo.transition(task.id, TaskStatus.AWAITING_CONFIRM)
        self._artifacts_repo.upsert(task.id, task.agent_type, artifacts=artifacts)
        _logger.info("task awaiting confirm", extra={"task_id": task.id})

    def fail(self, task, error: str, owner_id: Optional[float]) -> None:
        """先校验租约再翻转失败并写错误,漂移即放弃。"""
        if not self.valid(task.id, owner_id):
            _logger.warning("lease invalid, drop fail write", extra={"task_id": task.id, "error": error})
            return
        self._task_repo.transition(task.id, TaskStatus.FAILED)
        self._content_repo.set_error(task.id, error)
        self._progress_repo.set_signal(task.id, "这步失败了")
        _logger.info("task failed", extra={"task_id": task.id, "error": error})
