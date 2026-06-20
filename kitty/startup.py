"""应用启动副作用：装配完成后的数据 load / 回灌 / 清理。

装配（把对象 new 出来、注入依赖）在 kitty.app.create_app() 内联完成；
启动副作用（扫描技能、回灌设置、加载会话元数据 + 首次清理）在这里跑一次。
create_app 在装配后调用 run_startup(...)。
"""

from __future__ import annotations

from kitty.services.session import SessionService
from kitty.services.settings import SettingsService
from kitty.services.skill import SkillService


def run_startup(
    skill_service: SkillService,
    settings_service: SettingsService,
    session_service: SessionService,
) -> None:
    """装配后跑一次性的 load：技能扫描、设置回灌、会话元数据加载（含首次清理）。"""
    skill_service.load()
    settings_service.load_all()
    session_service.load()
