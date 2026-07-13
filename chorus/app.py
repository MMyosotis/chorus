"""FastAPI 应用工厂：内联装配所有服务、agent、工具、钩子与调度器。

只装配不启副作用，副作用经生命周期在启动时跑一次。HTTP 需要的服务挂应用状态。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chorus.agents.loop import AgentLoop
from chorus.agents.scheduler import TaskScheduler
from chorus.agents.subagent import SubAgentService
from chorus.agents.supervisor import SupervisorService
from chorus.config import (
    DATA_DIR,
    MAX_TOKENS,
    SCHEDULER_INTERVAL,
    ZOMBIE_TIMEOUT,
)
from chorus.agents.chat_model import ChatModelProvider
from chorus.domain.skill import SkillLoader
from chorus.domain.title import TitleGenerationService
from chorus.domain.task.aside import AsideGenerator
from chorus.hooks import ErrorFinalizer, HookRegistry, TitlePostProcessor, TraceEmitter, emit_message_start
from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.session import SessionRepository
from chorus.repo.settings import SettingsRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.routes.agents import router as agents_router
from chorus.routes.chat import router as chat_router
from chorus.routes.sessions import router as sessions_router
from chorus.routes.settings import router as settings_router
from chorus.routes.settings import settings_router as model_options_router
from chorus.routes.task import router as task_router
from chorus.services.message import MessageService
from chorus.services.intent_state import IntentStateService
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService
from chorus.services.task import TaskService
from chorus.services.trace import TraceService
from chorus.startup import run_startup
from chorus.tools import build_tool_dispatch


def create_app() -> FastAPI:
    skill_loader = SkillLoader()

    conn = ConnectionFactory(DATA_DIR / "chorus.db")
    settings_service = SettingsService(SettingsRepository(conn))
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    intent_repo = IntentStateRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    task_artifacts_repo = TaskArtifactsRepository(conn)
    task_progress_repo = TaskProgressRepository(conn)
    task_content_repo = TaskContentRepository(conn)
    session_service = SessionService(session_repo)
    trace_service = TraceService(trace_repo)
    message_service = MessageService(msg_repo, trace_service)
    intent_state_service = IntentStateService(intent_repo, session_service)

    chat_models = ChatModelProvider(settings_service)
    # 标题生成固定用默认模型，不随用户当前设置变动
    title_entry = chat_models.title_entry()
    title_service = TitleGenerationService(title_entry.client, title_entry.model_id)
    aside_generator = AsideGenerator(title_entry.client, title_entry.model_id)

    tool_dispatcher = build_tool_dispatch(
        settings_service, task_repo, task_content_repo, skill_loader, intent_state_service,
    )

    hooks = HookRegistry()
    trace = TraceEmitter(trace_service, tool_dispatcher, MAX_TOKENS)
    hooks.register("TurnStart", emit_message_start, source="supervisor")
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Stop", TitlePostProcessor(session_service, message_service, title_service).on_stop)
    hooks.register("Error", ErrorFinalizer(message_service).on_error)

    agent_loop = AgentLoop(hooks, tool_dispatcher, MAX_TOKENS)

    supervisor_service = SupervisorService(
        session_service, message_service, hooks,
        chat_models, task_repo,
        tool_dispatcher, agent_loop, intent_state_service, skill_loader,
    )
    subagent_service = SubAgentService(
        message_service, task_repo, task_artifacts_repo,
        task_progress_repo, task_content_repo,
        tool_dispatcher, chat_models,
        agent_loop, aside_generator, skill_loader,
    )
    task_service = TaskService(
        task_repo, task_artifacts_repo,
        task_progress_repo, task_content_repo, session_service,
    )
    scheduler = TaskScheduler(
        task_repo, trace_service, subagent_service.run, session_service,
        SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT,
    )

    app = FastAPI(
        title="Chorus",
        version="0.3.0",
        lifespan=_build_lifespan(settings_service, scheduler),
    )
    app.state.session_service = session_service
    app.state.message_service = message_service
    app.state.trace_service = trace_service
    app.state.intent_state_service = intent_state_service
    app.state.supervisor_service = supervisor_service
    app.state.task_service = task_service
    app.state.scheduler = scheduler
    app.state.settings_service = settings_service
    app.state.tool_dispatch = tool_dispatcher

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(sessions_router)
    app.include_router(agents_router)
    app.include_router(chat_router)
    app.include_router(task_router)
    app.include_router(settings_router)
    app.include_router(model_options_router)
    return app


def _build_lifespan(settings_service, scheduler):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        run_startup(scheduler)
        yield
        scheduler.stop()
    return _lifespan


app = create_app()
