# kitty/agents/scheduler.py
"""TaskScheduler：同进程后台调度器线程，轮询数据库派发可执行 task + 回收 zombie。

无 LLM loop、无事件点可挂 hook——schedule 事件（dispatch/cas_conflict/zombie_reclaim）
直接内联 trace.add 写库。用 BoundedSemaphore(POOL_SIZE) 限流：try acquire 非阻塞，
失败则跳过该 task（仍 pending 未 CAS），下轮再试；成功则 CAS pending→running + submit
subagent.run（worker 完成时 release）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from kitty.config import POOL_SIZE, SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT
from kitty.domain.task import TaskStatus, can_schedule
from kitty.domain.trace import TraceEntry, TracePhase
from kitty.repositories.task import TaskRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.session import SessionService

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(
        self,
        task_repo: TaskRepository,
        trace_repo: TraceRepository,
        subagent_run,                       # callable(task_id) -> None
        session_service: SessionService,    # 预留：未来 session 级协调（app.py 装配时传入）
        interval: float = SCHEDULER_INTERVAL,
        zombie_timeout: int = ZOMBIE_TIMEOUT,
        pool_size: int = POOL_SIZE,
        clock=time.time,
    ):
        self._task_repo = task_repo
        self._trace_repo = trace_repo
        self._subagent_run = subagent_run
        self._session = session_service
        self._interval = interval
        self._zombie_timeout = zombie_timeout
        self._clock = clock
        self._semaphore = threading.BoundedSemaphore(pool_size)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        """启动后台线程（先 zombie 回收，再周期 _tick）。幂等。"""
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
        """一轮：扫描 pending task，可调度则 CAS+submit；回收 zombie。"""
        for task, deps in self._task_repo.find_pending_with_deps():
            self._try_schedule_one(task, deps)
        self._reclaim_zombies()

    def _try_schedule_one(self, task, deps) -> None:
        if not can_schedule(task, deps):
            return
        # 限流：非阻塞 acquire，满则跳过（task 仍 pending，下轮再试）
        if not self._semaphore.acquire(blocking=False):
            return
        ok = self._task_repo.cas_update(
            task.id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value,
        )
        if not ok:
            self._semaphore.release()
            self._trace_schedule(task.id, "cas_conflict", TaskStatus.PENDING.value, TaskStatus.RUNNING.value,
                                 "CAS 失败（状态已漂移）")
            return
        self._trace_schedule(task.id, "dispatch", TaskStatus.PENDING.value, TaskStatus.RUNNING.value, "")
        # submit 到独立线程跑 subagent，完成时 release semaphore
        threading.Thread(
            target=self._run_worker, args=(task.id,), name=f"subagent-{task.id}", daemon=True,
        ).start()

    def _run_worker(self, task_id: str) -> None:
        try:
            self._subagent_run(task_id)
        except Exception:  # noqa: BLE001
            logger.exception("subagent worker %s crashed", task_id)
        finally:
            self._semaphore.release()

    def _reclaim_zombies(self) -> None:
        """回收 running 且心跳超时的 task：CAS running→pending。"""
        now = self._clock()
        for task in self._task_repo.find_running_before(now - self._zombie_timeout):
            ok = self._task_repo.cas_update(
                task.id, TaskStatus.RUNNING.value, TaskStatus.PENDING.value,
            )
            if ok:
                self._trace_schedule(task.id, "zombie_reclaim",
                                     TaskStatus.RUNNING.value, TaskStatus.PENDING.value,
                                     f"心跳超时 {self._zombie_timeout}s")

    def _trace_schedule(self, task_id: str, event: str, from_status: str, to_status: str, detail: str) -> None:
        """内联写 schedule trace（scheduler 无 LLM loop，不挂 hook）。fail-open。"""
        try:
            task = self._task_repo.get(task_id)
            if task is None:
                return
            self._trace_repo.add(TraceEntry(
                session_id=task.session_id, task_id=task_id, source="scheduler",
                phase=TracePhase.SCHEDULE, ts=self._clock(),
                payload={"event": event, "task_id": task_id, "from_status": from_status,
                         "to_status": to_status, "detail": detail},
            ))
        except Exception:  # noqa: BLE001 — trace fail-open
            logger.warning("scheduler trace 写入失败 task=%s event=%s", task_id, event)
