"""依赖注入入口：从应用状态取服务，路由端点用 Depends 拿到，不引模块级单例。"""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import Request

from chorus.agents.scheduler import TaskScheduler
from chorus.agents.supervisor import SupervisorService
from chorus.domain.skill import SkillLoader
from chorus.services.intent_state import IntentStateService
from chorus.services.memory import MemoryService
from chorus.services.message import MessageService
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService
from chorus.services.task import TaskService
from chorus.services.trace import TraceService
from chorus.tools import ToolDispatch

_T = TypeVar("_T")


def _provider(attr: str, cls: type[_T]) -> Callable[[Request], _T]:
    def provide(request: Request) -> _T:
        return getattr(request.app.state, attr)
    provide.__name__ = f"provide_{attr}"
    return provide


provide_session_service = _provider("session_service", SessionService)
provide_message_service = _provider("message_service", MessageService)
provide_trace_service = _provider("trace_service", TraceService)
provide_intent_state_service = _provider("intent_state_service", IntentStateService)
provide_option_service = _provider("option_service", OptionPromptService)
provide_settings_service = _provider("settings_service", SettingsService)
provide_memory_service = _provider("memory_service", MemoryService)
provide_supervisor_service = _provider("supervisor_service", SupervisorService)
provide_task_service = _provider("task_service", TaskService)
provide_scheduler = _provider("scheduler", TaskScheduler)
provide_tool_dispatch = _provider("tool_dispatch", ToolDispatch)
provide_skill_loader = _provider("skill_loader", SkillLoader)
