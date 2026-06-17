"""FastAPI 依赖注入入口：从 app.state.container 取 Service。

路由端点用 `Depends(provide_xxx)` 拿到 Service，不再 import 模块级单例。
"""

from __future__ import annotations

from fastapi import Depends, Request

from kitty.container import AppContainer
from kitty.services.chat import ChatService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService


def provide_container(request: Request) -> AppContainer:
    return request.app.state.container


def provide_session_service(
    container: AppContainer = Depends(provide_container),
) -> SessionService:
    return container.session_service


def provide_chat_service(
    container: AppContainer = Depends(provide_container),
) -> ChatService:
    return container.chat_service


def provide_settings_service(
    container: AppContainer = Depends(provide_container),
) -> SettingsService:
    return container.settings_service
