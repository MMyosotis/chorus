"""应用启动副作用：装配完成后的数据 load / 回灌 / 清理。

与 AppContainer 的职责分离：AppContainer 只负责"把对象 new 出来、注入依赖"，
启动副作用（扫描技能、回灌设置、加载会话元数据 + 首次清理）在这里跑一次。
create_app 在装配后调用 run_startup(container)。
"""

from __future__ import annotations

from kitty.container import AppContainer


def run_startup(container: AppContainer) -> None:
    """装配后跑一次性的 load：技能扫描、设置回灌、会话元数据加载（含首次清理）。"""
    container.skill_service.load()
    container.settings_service.load_all()
    container.session_service.load()
