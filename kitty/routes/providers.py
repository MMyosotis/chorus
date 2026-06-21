"""FastAPI 依赖注入入口：从 app.state 取 Service。

路由端点用 `Depends(provide_xxx)` 拿到 Service，不 import 模块级单例。
"""

from __future__ import annotations

from fastapi import Request

from kitty.services.chat import ChatService
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService


def provide_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def provide_message_service(request: Request) -> MessageService:
    return request.app.state.message_service


def provide_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def provide_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service
