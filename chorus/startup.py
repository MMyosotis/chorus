"""应用启动副作用：装配完成后的数据 load / 清理 + scheduler 启动。"""
from __future__ import annotations

from chorus.agents.scheduler import TaskScheduler
from chorus.services.session import SessionService


def run_startup(
    session_service: SessionService,
    scheduler: TaskScheduler,
) -> None:
    session_service.load()
    scheduler.start()
