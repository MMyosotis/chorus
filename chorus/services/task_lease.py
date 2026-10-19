"""任务租约守卫:终态写入以条件翻转为准,归属漂移即丢弃产物。"""
from __future__ import annotations

from chorus.domain.log import get_logger
from chorus.domain.task import TaskStatus
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository

_logger = get_logger("lease")


class LeaseGuard:
    """任务终态写入守卫:条件翻转保证只有现任执行者能落终态与产物。"""

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

    def valid(self, task_id: str, owner_id: str) -> bool:
        """入口早退优化，非正确性屏障；正确性由每轮心跳与终态条件翻转保证。"""
        latest = self._task_repo.get(task_id)
        return latest is not None and latest.status == TaskStatus.RUNNING and latest.owner_id == owner_id

    def finalize(self, task, artifacts, owner_id: str) -> None:
        """只有当前执行者仍在运行，才翻转待复核并落产物。"""
        if not self._task_repo.transition_owned(
            task.id, TaskStatus.AWAITING_CONFIRM,
            expected_status=TaskStatus.RUNNING, owner_id=owner_id,
        ):
            _logger.warning("lease invalid, drop finalize", extra={"task_id": task.id})
            return
        self._artifacts_repo.upsert(task.id, task.agent_type, artifacts=artifacts)
        _logger.info("task awaiting confirm", extra={"task_id": task.id})

    def fail(self, task, error: str, owner_id: str) -> None:
        """只有当前执行者仍在运行，才翻转失败并写错误。"""
        if not self._task_repo.transition_owned(
            task.id, TaskStatus.FAILED,
            expected_status=TaskStatus.RUNNING, owner_id=owner_id,
        ):
            _logger.warning("lease invalid, drop fail write", extra={"task_id": task.id, "error": error})
            return
        self._content_repo.set_error(task.id, error)
        self._progress_repo.set_signal(task.id, "这步失败了")
        _logger.info("task failed", extra={"task_id": task.id, "error": error})
