"""任务调度器：后台线程轮询数据库派发可执行任务，并回收僵死任务。

无模型循环，调度事件直接内联写轨迹。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from chorus.config import SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT
from chorus.domain.task import TaskStatus
from chorus.domain.trace import Schedule, TracePhase
from chorus.repo.task import TaskRepository
from chorus.services.session import SessionService
from chorus.services.trace import TraceService


class TaskScheduler:
    def __init__(
        self,
        task_repo: TaskRepository,
        trace_service: TraceService,
        subagent_run,
        session_service: SessionService,
        interval: float = SCHEDULER_INTERVAL,
        zombie_timeout: int = ZOMBIE_TIMEOUT,
    ):
        self._task_repo = task_repo
        self._trace = trace_service
        self._subagent_run = subagent_run
        self._session = session_service
        self._interval = interval
        self._zombie_timeout = zombie_timeout
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
            pass

    def _tick(self) -> None:
        """一轮：扫描待执行任务，可调度则翻转并提交，再回收僵死。"""
        for task, deps in self._task_repo.find_pending_with_deps():
            self._try_schedule_one(task, deps)
        self._reclaim_zombies()

    def _try_schedule_one(self, task, deps) -> None:
        if not task.can_schedule(deps):
            return

        # 占槽：翻转为运行中并写入租约归属标识
        if not self._task_repo.claim(task.id, time.time()):
            self._trace_schedule(task.session_id, Schedule(
                event="cas_conflict", task_id=task.id,
                from_status=TaskStatus.PENDING, to_status=TaskStatus.RUNNING,
                detail="CAS 失败（状态已漂移）",
            ))
            return

        self._trace_schedule(task.session_id, Schedule(
            event="dispatch", task_id=task.id,
            from_status=TaskStatus.PENDING, to_status=TaskStatus.RUNNING, detail="",
        ))

        # 提交独立线程跑子 agent
        threading.Thread(
            target=self._run_worker, args=(task.id,), name=f"subagent-{task.id}", daemon=True,
        ).start()

    def _run_worker(self, task_id: str) -> None:
        try:
            self._subagent_run(task_id)
        except Exception:  # noqa: BLE001
            pass

    def _reclaim_zombies(self) -> None:
        """回收运行且心跳超时的任务，翻回待执行。"""
        now = time.time()
        for task in self._task_repo.find_running_before(now - self._zombie_timeout):
            self._task_repo.transition(task.id, TaskStatus.RUNNING, TaskStatus.PENDING)
            self._trace_schedule(task.session_id, Schedule(
                event="zombie_reclaim", task_id=task.id,
                from_status=TaskStatus.RUNNING, to_status=TaskStatus.PENDING,
                detail=f"心跳超时 {self._zombie_timeout}s",
            ))

    def _trace_schedule(self, session_id: str, schedule: Schedule) -> None:
        """内联写调度轨迹，失败不阻断。"""
        try:
            self._trace.add_trace(
                session_id=session_id, task_id=schedule.task_id, source="scheduler",
                phase=TracePhase.SCHEDULE, payload=schedule,
            )
        except Exception:  # noqa: BLE001 — trace fail-open
            pass
