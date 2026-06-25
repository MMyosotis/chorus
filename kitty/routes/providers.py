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


from kitty.agents.scheduler import TaskScheduler
from kitty.agents.supervisor import SupervisorService
from kitty.services.task import TaskService


def provide_supervisor_service(request: Request) -> SupervisorService:
    return request.app.state.supervisor_service


def provide_task_service(request: Request) -> TaskService:
    return request.app.state.task_service


def provide_scheduler(request: Request) -> TaskScheduler:
    return request.app.state.scheduler
