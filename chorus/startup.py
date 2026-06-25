"""应用启动副作用：装配完成后的数据 load / 回灌 / 清理 + scheduler 启动。"""
from __future__ import annotations

from chorus.agents.scheduler import TaskScheduler
from chorus.domain.skill import SkillLoader
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService


def run_startup(
    skill_loader: SkillLoader,
    settings_service: SettingsService,
    session_service: SessionService,
    scheduler: TaskScheduler,
) -> None:
    skill_loader.load()
    settings_service.load_all()
    session_service.load()
    scheduler.start()
