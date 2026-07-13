"""依赖注入入口：从应用状态取服务，路由端点用 Depends 拿到，不引模块级单例。"""

from __future__ import annotations

from fastapi import Request

from chorus.services.message import MessageService
from chorus.services.intent_state import IntentStateService
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService
from chorus.services.trace import TraceService


def provide_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def provide_message_service(request: Request) -> MessageService:
    return request.app.state.message_service


def provide_trace_service(request: Request) -> TraceService:
    return request.app.state.trace_service


def provide_intent_state_service(request: Request) -> IntentStateService:
    return request.app.state.intent_state_service


def provide_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


from chorus.agents.scheduler import TaskScheduler
from chorus.agents.supervisor import SupervisorService
from chorus.services.task import TaskService
from chorus.tools import ToolDispatch


def provide_supervisor_service(request: Request) -> SupervisorService:
    return request.app.state.supervisor_service


def provide_task_service(request: Request) -> TaskService:
    return request.app.state.task_service


def provide_scheduler(request: Request) -> TaskScheduler:
    return request.app.state.scheduler


def provide_tool_dispatch(request: Request) -> ToolDispatch:
    return request.app.state.tool_dispatch
