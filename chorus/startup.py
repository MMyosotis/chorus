"""应用启动副作用：装配完成后的 scheduler 启动。"""
from __future__ import annotations

from chorus.agents.scheduler import TaskScheduler


def run_startup(scheduler: TaskScheduler) -> None:
    scheduler.start()
