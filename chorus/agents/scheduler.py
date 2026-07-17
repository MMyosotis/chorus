"""任务调度器：后台线程轮询数据库派发可执行任务，并回收僵死任务。

无模型循环，调度与回收行为经日志留痕，不进 trace。吞异常处记日志保留栈，周期顺带清理过期日志。
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from chorus.config import SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT
from chorus.domain.log import cleanup_old_logs, get_logger
from chorus.domain.task import TaskStatus
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.services.session import SessionService

_logger = get_logger("scheduler")


class TaskScheduler:
    def __init__(
        self,
        task_repo: TaskRepository,
        subagent_run,
        session_service: SessionService,
        content_repo: TaskContentRepository,
        progress_repo: TaskProgressRepository,
        interval: float = SCHEDULER_INTERVAL,
        zombie_timeout: int = ZOMBIE_TIMEOUT,
        *,
        log_dir: Optional[Path] = None,
        log_retention_days: int = 0,
        log_cleanup_interval: int = 0,
    ):
        self._task_repo = task_repo
        self._subagent_run = subagent_run
        self._session = session_service
        self._content_repo = content_repo
        self._progress_repo = progress_repo
        self._interval = interval
        self._zombie_timeout = zombie_timeout
        self._log_dir = log_dir
        self._log_retention_days = log_retention_days
        self._log_cleanup_interval = log_cleanup_interval
        self._last_log_cleanup = 0.0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        """启动后台线程，先回收僵死再周期轮询。"""
        self._stop.clear()
        self._reclaim_zombies()
        self._thread = threading.Thread(target=self._loop, name="task-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._interval * 2)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._tick_guarded()
            self._stop.wait(self._interval)

    def _tick_guarded(self) -> None:
        """单轮调度，单轮异常不外抛以免打死调度线程。"""
        try:
            self._tick()
        except Exception:  # noqa: BLE001 — 调度器不能因单轮异常退出
            _logger.exception("scheduler tick failed")

    def _tick(self) -> None:
        """一轮：扫描待执行任务，可调度则翻转并提交，再回收僵死，顺带清旧日志。"""
        for task, deps in self._task_repo.find_pending_with_deps():
            self._try_schedule_one(task, deps)
        self._reclaim_zombies()
        self._maybe_cleanup_logs()

    def _maybe_cleanup_logs(self) -> None:
        """按清理间隔删除过期日志，失败不阻断。"""
        if self._log_dir is None or self._log_cleanup_interval <= 0:
            return
        now = time.time()
        if now - self._last_log_cleanup < self._log_cleanup_interval:
            return
        self._last_log_cleanup = now
        try:
            removed = cleanup_old_logs(self._log_dir, self._log_retention_days)
            if removed:
                _logger.info("cleaned %d expired log files", removed)
        except Exception:  # noqa: BLE001 — 清理失败不杀调度
            _logger.warning("log cleanup failed", exc_info=True)

    def _try_schedule_one(self, task, deps) -> None:
        if not task.can_schedule(deps):
            return

        # 占槽：设为运行中并写租约归属，行已不存在则跳过
        if not self._task_repo.claim(task.id, time.time()):
            return

        _logger.info("dispatch task", extra={"session_id": task.session_id, "task_id": task.id})

        # 提交独立线程跑子 agent
        threading.Thread(
            target=self._run_worker, args=(task.id,), name=f"subagent-{task.id}", daemon=True,
        ).start()

    def _run_worker(self, task_id: str) -> None:
        try:
            self._subagent_run(task_id)
        except Exception:  # noqa: BLE001 - 后台线程崩溃留栈
            _logger.exception("subagent thread crashed", extra={"task_id": task_id})

    def _reclaim_zombies(self) -> None:
        """回收运行且心跳超时的任务，翻为失败交人工重跑。"""
        now = time.time()
        for task in self._task_repo.find_running_before(now - self._zombie_timeout):
            self._task_repo.transition(task.id, TaskStatus.FAILED)
            self._content_repo.set_error(task.id, "运行超时未响应")
            self._progress_repo.set_signal(task.id, "这步失败了")
            _logger.warning("zombie reclaim", extra={"session_id": task.session_id, "task_id": task.id})
