"""FastAPI 应用工厂：create_app 内联装配所有 Service / Agent / Tool / Hook / Scheduler。

create_app 只装配（new + 注入），不含启动副作用——副作用经 lifespan 在服务启动时
跑一次。HTTP 需要的 service 挂 app.state，路由经 Depends 取用。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chorus.agents.scheduler import TaskScheduler
from chorus.agents.subagent import SubAgentService
from chorus.agents.supervisor import SupervisorService
from chorus.config import (
    BAIDU_SEARCH_API_KEY,
    BAIDU_SEARCH_BASE_URL,
    DATA_DIR,
    MAX_TOKENS,
    POOL_SIZE,
    SCHEDULER_INTERVAL,
    ZOMBIE_TIMEOUT,
)
from chorus.agents.chat_model import ChatModelProvider
from chorus.domain.skill import SkillLoader
from chorus.domain.title import TitleGenerationService
from chorus.hooks import ErrorFinalizer, HookRegistry, TitlePostProcessor, TraceEmitter
from chorus.repositories.connection import ConnectionFactory
from chorus.repositories.message import MessageRepository
from chorus.repositories.session import SessionRepository
from chorus.repositories.settings import SettingsRepository
from chorus.repositories.task import TaskRepository
from chorus.repositories.task_artifacts import TaskArtifactsRepository
from chorus.repositories.task_steps import TaskStepsRepository
from chorus.repositories.trace import TraceRepository
from chorus.routes.chat import router as chat_router
from chorus.routes.sessions import router as sessions_router
from chorus.routes.settings import router as settings_router
from chorus.routes.settings import settings_router as model_options_router
from chorus.routes.task import router as task_router
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService
from chorus.services.task import TaskService
from chorus.startup import run_startup
from chorus.tools import ToolContext, ToolCtxFactory, ToolRegistry
from chorus.tools.builtin import BaiduSearchTool, CreatePlanTool, LoadSkillTool, OutputPlanTool
from chorus.tools.builtin.generate_image import GenerateImageTool
from chorus.tools.clients.baidu_search import BaiduSearchClient
from chorus.tools.image_model import ImageModelProvider


def create_app() -> FastAPI:
    skill_loader = SkillLoader()

    conn = ConnectionFactory(DATA_DIR / "chorus.db")
    settings_service = SettingsService(SettingsRepository(conn))
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    task_artifacts_repo = TaskArtifactsRepository(conn)
    task_steps_repo = TaskStepsRepository(conn)
    session_service = SessionService(session_repo)
    message_service = MessageService(msg_repo, trace_repo)

    chat_models = ChatModelProvider(settings_service)
    # 标题生成固定用默认模型（不随用户当前对话设置变动）
    title_entry = chat_models.title_entry()
    title_service = TitleGenerationService(title_entry.client, title_entry.model_id)

    image_models = ImageModelProvider(settings_service)

    baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
    tool_registry = ToolRegistry([
        LoadSkillTool(),
        OutputPlanTool(),
        GenerateImageTool(settings_service, image_models),
        BaiduSearchTool(baidu_client),
        CreatePlanTool(task_repo, conn),
    ])

    def tool_ctx_factory(session_id):
        return ToolContext(skill_loader=skill_loader, session_id=session_id)

    hooks = HookRegistry()
    trace = TraceEmitter(message_service, MAX_TOKENS)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Stop", TitlePostProcessor(session_service, message_service, title_service).on_stop)
    hooks.register("Error", ErrorFinalizer(message_service).on_error)

    all_tool_schemas = tool_registry.schemas_openai()

    supervisor_service = SupervisorService(
        session_service, message_service, skill_loader, hooks,
        chat_models, MAX_TOKENS, task_repo,
        tool_registry, tool_ctx_factory,
    )
    subagent_service = SubAgentService(
        conn, message_service, task_repo, task_artifacts_repo, task_steps_repo,
        tool_registry, tool_ctx_factory, hooks, chat_models,
        MAX_TOKENS, all_tool_schemas,
    )
    task_service = TaskService(task_repo, task_artifacts_repo, task_steps_repo, session_service)
    scheduler = TaskScheduler(
        task_repo, trace_repo, subagent_service.run, session_service,
        SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT, POOL_SIZE,
    )

    app = FastAPI(
        title="Chorus",
        version="0.3.0",
        lifespan=_build_lifespan(skill_loader, settings_service, session_service, scheduler),
    )
    app.state.session_service = session_service
    app.state.message_service = message_service
    app.state.supervisor_service = supervisor_service
    app.state.task_service = task_service
    app.state.scheduler = scheduler
    app.state.settings_service = settings_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(task_router)
    app.include_router(settings_router)
    app.include_router(model_options_router)
    return app


def _build_lifespan(skill_loader, settings_service, session_service, scheduler):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        run_startup(skill_loader, session_service, scheduler)
        yield
        scheduler.stop()
    return _lifespan


app = create_app()
