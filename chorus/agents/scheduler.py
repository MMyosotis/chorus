"""任务调度器：后台线程轮询数据库派发可执行任务，并回收僵死任务。

无模型循环、无钩子事件点，调度事件直接内联写轨迹。用信号量限流：非阻塞获取，满则
跳过该任务下轮再试；成功则翻转状态为运行中并提交子 agent 执行。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from chorus.config import POOL_SIZE, SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT
from chorus.domain.task import TaskStatus, can_schedule
from chorus.domain.trace import TracePhase
from chorus.repo.task import TaskRepository
from chorus.services.session import SessionService
from chorus.services.trace import TraceService

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(
        self,
        task_repo: TaskRepository,
        trace_service: TraceService,
        subagent_run,
        session_service: SessionService,
        interval: float = SCHEDULER_INTERVAL,
        zombie_timeout: int = ZOMBIE_TIMEOUT,
        pool_size: int = POOL_SIZE,
    ):
        self._task_repo = task_repo
        self._trace = trace_service
        self._subagent_run = subagent_run
        self._session = session_service
        self._interval = interval
        self._zombie_timeout = zombie_timeout
        self._semaphore = threading.BoundedSemaphore(pool_size)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        """启动后台线程，先回收僵死再周期轮询。幂等。"""
        if self._thread is not None:
            return
        self._stop.clear()
        self._reclaim_zombies()
        self._thread = threading.Thread(target=self._loop, name="task-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=self._interval * 2)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:  # noqa: BLE001 — 调度器不能因单轮异常退出
                logger.exception("scheduler tick failed")
            self._stop.wait(self._interval)

    def _tick(self) -> None:
        """一轮：扫描待执行任务，可调度则翻转并提交，再回收僵死。"""
        for task, deps in self._task_repo.find_pending_with_deps():
            self._try_schedule_one(task, deps)
        self._reclaim_zombies()

    def _try_schedule_one(self, task, deps) -> None:
        if not can_schedule(task, deps):
            return
        # 限流：非阻塞获取，满则跳过下轮再试
        if not self._semaphore.acquire(blocking=False):
            return
        # 翻转为运行中并写 owner_id 作为租约归属 token
        now = time.time()
        ok = self._task_repo.cas_update(
            task.id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value,
            owner_id=now, updated_at=now,
        )
        if not ok:
            self._semaphore.release()
            self._trace_schedule(task.id, "cas_conflict", TaskStatus.PENDING.value, TaskStatus.RUNNING.value,
                                 "CAS 失败（状态已漂移）")
            return
        self._trace_schedule(task.id, "dispatch", TaskStatus.PENDING.value, TaskStatus.RUNNING.value, "")
        # 提交独立线程跑子 agent，完成时释放槽位
        try:
            threading.Thread(
                target=self._run_worker, args=(task.id,), name=f"subagent-{task.id}", daemon=True,
            ).start()
        except Exception:
            # 启动失败：回滚状态并释放槽位，下轮重试
            self._semaphore.release()
            self._task_repo.cas_update(task.id, TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
            logger.exception("scheduler failed to spawn worker for %s", task.id)

    def _run_worker(self, task_id: str) -> None:
        try:
            self._subagent_run(task_id)
        except Exception:  # noqa: BLE001
            logger.exception("subagent worker %s crashed", task_id)
        finally:
            self._semaphore.release()

    def _reclaim_zombies(self) -> None:
        """回收运行且心跳超时的任务，翻回待执行。"""
        now = time.time()
        for task in self._task_repo.find_running_before(now - self._zombie_timeout):
            ok = self._task_repo.cas_update(
                task.id, TaskStatus.RUNNING.value, TaskStatus.PENDING.value,
            )
            if ok:
                self._trace_schedule(task.id, "zombie_reclaim",
                                     TaskStatus.RUNNING.value, TaskStatus.PENDING.value,
                                     f"心跳超时 {self._zombie_timeout}s")

    def _trace_schedule(self, task_id: str, event: str, from_status: str, to_status: str, detail: str) -> None:
        """内联写调度轨迹，失败只记日志。"""
        try:
            task = self._task_repo.get(task_id)
            if task is None:
                return
            self._trace.add_trace(
                session_id=task.session_id, task_id=task_id, source="scheduler",
                phase=TracePhase.SCHEDULE,
                payload={"event": event, "task_id": task_id, "from_status": from_status,
                         "to_status": to_status, "detail": detail},
            )
        except Exception:  # noqa: BLE001 — trace fail-open
            logger.warning("scheduler trace 写入失败 task=%s event=%s", task_id, event)
