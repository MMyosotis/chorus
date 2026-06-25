"""FastAPI 应用工厂：create_app 内联装配所有 Service / Agent / Tool / Hook / Scheduler。

create_app 只装配（new + 注入），不含启动副作用——副作用经 lifespan 在服务启动时
跑一次。HTTP 需要的 service 挂 app.state，路由经 Depends 取用。
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from kitty.agents.scheduler import TaskScheduler
from kitty.agents.subagent import SubAgentService
from kitty.agents.supervisor import ChatModelEntry, SupervisorService
from kitty.config import (
    BAIDU_SEARCH_API_KEY,
    BAIDU_SEARCH_BASE_URL,
    CHAT_MODELS,
    DATA_DIR,
    DEFAULT_CHAT_MODEL_ID,
    DEFAULT_IMAGE_MODEL_ID,
    IMAGE_MODELS,
    IMAGE_TEST_FAKE_URL,
    MAX_TOKENS,
    POOL_SIZE,
    SCHEDULER_INTERVAL,
    SUBAGENT_MODELS,
    ZOMBIE_TIMEOUT,
)
from kitty.domain.skill import SkillLoader
from kitty.domain.title import TitleGenerationService
from kitty.hooks import HookRegistry, RollbackHandler, TitlePostProcessor, TraceEmitter
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.settings import SettingsRepository
from kitty.repositories.task import TaskRepository
from kitty.repositories.task_artifacts import TaskArtifactsRepository
from kitty.repositories.task_steps import TaskStepsRepository
from kitty.repositories.trace import TraceRepository
from kitty.routes.chat import router as chat_router
from kitty.routes.sessions import router as sessions_router
from kitty.routes.settings import router as settings_router
from kitty.routes.settings import settings_router as model_options_router
from kitty.routes.task import router as task_router
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService
from kitty.services.task import TaskService
from kitty.startup import run_startup
from kitty.tools import ToolContext, ToolCtxFactory, ToolRegistry
from kitty.tools.builtin import BaiduSearchTool, LoadSkillTool, OutputPlanTool
from kitty.tools.builtin.generate_image import GenerateImageTool, ImageModelEntry
from kitty.tools.clients.ark_image import ArkImageClient
from kitty.tools.clients.baidu_search import BaiduSearchClient


def create_app() -> FastAPI:
    skill_loader = SkillLoader()

    settings_service = SettingsService(
        SettingsRepository(ConnectionFactory(DATA_DIR / "settings.db"))
    )

    conn = ConnectionFactory(DATA_DIR / "little-kitty.db")
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    task_artifacts_repo = TaskArtifactsRepository(conn)
    task_steps_repo = TaskStepsRepository(conn)
    session_service = SessionService(session_repo)
    message_service = MessageService(msg_repo, trace_repo)

    chat_models: dict[str, ChatModelEntry] = {}
    for m in CHAT_MODELS:
        api_key = os.environ.get(m["api_key_env"], "")
        chat_models[m["id"]] = ChatModelEntry(
            client=OpenAI(api_key=api_key, base_url=m["base_url"], max_retries=3),
            model_id=m["model_id"],
        )
    default_entry = chat_models.get(DEFAULT_CHAT_MODEL_ID)
    if default_entry is None:
        raise RuntimeError(f"DEFAULT_CHAT_MODEL_ID={DEFAULT_CHAT_MODEL_ID!r} 不在 CHAT_MODELS 中")
    title_service = TitleGenerationService(default_entry.client, default_entry.model_id)

    image_models: dict[str, ImageModelEntry] = {}
    for m in IMAGE_MODELS:
        api_key = os.environ.get(m["api_key_env"], "")
        image_models[m["id"]] = ImageModelEntry(
            client=ArkImageClient(api_key, m["base_url"]), model_id=m["model_id"],
        )
    if DEFAULT_IMAGE_MODEL_ID not in image_models:
        raise RuntimeError(f"DEFAULT_IMAGE_MODEL_ID={DEFAULT_IMAGE_MODEL_ID!r} 不在 IMAGE_MODELS 中")

    baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
    tool_registry = ToolRegistry([
        LoadSkillTool(),
        OutputPlanTool(),
        GenerateImageTool(
            settings_service.get_image_test_mode, IMAGE_TEST_FAKE_URL,
            image_models, DEFAULT_IMAGE_MODEL_ID,
        ),
        BaiduSearchTool(baidu_client),
    ])

    def tool_ctx_factory(session_id, image_model=None):
        return ToolContext(skill_loader=skill_loader, session_id=session_id, image_model=image_model)

    hooks = HookRegistry()
    trace = TraceEmitter(message_service, MAX_TOKENS)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Stop", TitlePostProcessor(session_service, message_service, title_service).on_stop)
    hooks.register("Error", RollbackHandler(message_service).on_error)

    all_tool_schemas = tool_registry.schemas_openai()

    supervisor_service = SupervisorService(
        session_service, message_service, skill_loader, hooks,
        chat_models, DEFAULT_CHAT_MODEL_ID, MAX_TOKENS, task_repo, conn,
    )
    subagent_service = SubAgentService(
        conn, message_service, task_repo, task_artifacts_repo, task_steps_repo,
        tool_registry, tool_ctx_factory, hooks, chat_models, SUBAGENT_MODELS,
        MAX_TOKENS, all_tool_schemas,
    )
    task_service = TaskService(task_repo, task_artifacts_repo, task_steps_repo, session_service)
    scheduler = TaskScheduler(
        task_repo, trace_repo, subagent_service.run, session_service,
        SCHEDULER_INTERVAL, ZOMBIE_TIMEOUT, POOL_SIZE,
    )

    app = FastAPI(
        title="Little Kitty",
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
        run_startup(skill_loader, settings_service, session_service, scheduler)
        yield
        scheduler.stop()
    return _lifespan


app = create_app()
