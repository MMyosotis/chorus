"""应用启动副作用：装配完成后的数据 load / 清理 + scheduler 启动。"""
from __future__ import annotations

from chorus.agents.scheduler import TaskScheduler
from chorus.domain.skill import SkillLoader
from chorus.services.session import SessionService


def run_startup(
    skill_loader: SkillLoader,
    session_service: SessionService,
    scheduler: TaskScheduler,
) -> None:
    skill_loader.load()
    session_service.load()
    scheduler.start()
