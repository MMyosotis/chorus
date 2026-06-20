"""FastAPI 应用工厂：create_app 内联装配所有 Service / Tool / Hook，
3 个 HTTP 需要的 service 挂 app.state，路由经 Depends 取用。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from kitty.config import (
    API_KEY,
    ARK_IMAGE_API_KEY,
    ARK_IMAGE_BASE_URL,
    ARK_IMAGE_MODELS,
    BAIDU_SEARCH_API_KEY,
    BAIDU_SEARCH_BASE_URL,
    BASE_URL,
    CONV_MAX_BYTES,
    CONV_MAX_COUNT,
    CONV_TTL_DAYS,
    DATA_DIR,
    IMAGE_TEST_FAKE_URL,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
    MODEL_ID,
    SKILLS_DIR,
)
from kitty.hooks.manager import HookManager
from kitty.hooks.registry import build_hooks
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.settings import SettingsRepository
from kitty.repositories.trace import TraceRepository
from kitty.routes.chat import router as chat_router
from kitty.routes.sessions import router as sessions_router
from kitty.routes.settings import router as settings_router
from kitty.services.chat import ChatService
from kitty.services.cleanup import CleanupService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService
from kitty.services.skill import SkillService
from kitty.services.title import TitleGenerationService
from kitty.startup import run_startup
from kitty.tools.base import ToolContext, ToolCtxFactory, ToolRegistry
from kitty.tools.builtin import (
    BaiduSearchTool,
    BashTool,
    EditFileTool,
    GenerateImageTool,
    GlobSearchTool,
    LoadSkillTool,
    ReadFileTool,
    WriteFileTool,
)
from kitty.tools.clients.ark_image import ArkImageClient
from kitty.tools.clients.baidu_search import BaiduSearchClient
from kitty.tools.workspace import WorkspacePolicy


def create_app() -> FastAPI:
    app = FastAPI(title="Little Kitty", version="0.2.0")

    # —— 装配：中间对象是局部变量，装配完即弃 ——
    skill_service = SkillService(SKILLS_DIR)

    settings_service = SettingsService(
        SettingsRepository(ConnectionFactory(DATA_DIR / "settings.db"))
    )

    conn = ConnectionFactory(DATA_DIR / "little-kitty.db")
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    cleanup_service = CleanupService(
        session_repo, msg_repo, CONV_TTL_DAYS, CONV_MAX_BYTES, CONV_MAX_COUNT
    )
    session_service = SessionService(session_repo, msg_repo, trace_repo, cleanup_service)

    openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    title_service = TitleGenerationService(openai_client, MODEL_ID)

    workspace_policy = WorkspacePolicy(Path.cwd())
    ark_client = ArkImageClient(ARK_IMAGE_API_KEY, ARK_IMAGE_BASE_URL, ARK_IMAGE_MODELS)
    baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
    tool_registry = ToolRegistry([
        BashTool(),
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        GlobSearchTool(),
        LoadSkillTool(),
        GenerateImageTool(
            settings_service.get_image_test_mode, IMAGE_TEST_FAKE_URL, ark_client
        ),
        BaiduSearchTool(baidu_client),
    ])

    def tool_ctx_factory(session_id: str | None) -> ToolContext:
        return ToolContext(
            workspace=workspace_policy,
            skill_service=skill_service,
            session_id=session_id,
        )

    hooks = HookManager(build_hooks(
        session_service, skill_service, title_service,
        MODEL_ID, MAX_TOKENS, tool_registry, tool_ctx_factory,
    ))
    chat_service = ChatService(
        session_service, hooks, openai_client,
        MODEL_ID, MAX_TOKENS, MAX_TOOL_ITERATIONS, tool_registry.schemas_openai(),
    )

    # —— 启动副作用 ——
    run_startup(skill_service, settings_service, session_service)

    # —— HTTP 需要的 3 个 service 挂 app.state ——
    app.state.session_service = session_service
    app.state.chat_service = chat_service
    app.state.settings_service = settings_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(settings_router)
    return app


app = create_app()
