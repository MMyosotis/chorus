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
    LOG_BACKUP_COUNT,
    LOG_CLEANUP_INTERVAL,
    LOG_DIR,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_RETENTION_DAYS,
)
from chorus.agents.chat_model import ChatModelProvider
from chorus.domain.compact import SummaryGenerationService
from chorus.domain.skill import SkillLoader
from chorus.domain.log import setup_logging
from chorus.domain.title import TitleGenerationService
from chorus.domain.memory import MemoryLLMService
from chorus.domain.task.aside import AsideGenerator
from chorus.hooks import HookRegistry, MemoryExtractor, TitlePostProcessor, TraceEmitter
from chorus.repo.creator_memory import CreatorMemoryRepository
from chorus.repo.engine import build_engine
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.option import OptionPromptRepository
from chorus.repo.session import SessionRepository
from chorus.repo.settings import SettingsRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.routes.agents import router as agents_router
from chorus.routes.chat import router as chat_router
from chorus.routes.memory import router as memory_router
from chorus.routes.sessions import router as sessions_router
from chorus.routes.settings import router as debug_router
from chorus.routes.settings import settings_router
from chorus.routes.skills import router as skills_router
from chorus.routes.task import router as task_router
from chorus.services.compact import CompactService
from chorus.services.memory import MemoryService
from chorus.services.message import MessageService
from chorus.services.intent_state import IntentStateService
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService
from chorus.services.task import TaskService
from chorus.services.task_lease import LeaseGuard
from chorus.services.trace import TraceService
from chorus.startup import run_startup
from chorus.tools import build_tool_dispatch


def create_app() -> FastAPI:
    skill_loader = SkillLoader()

    engine = build_engine(DATA_DIR / "chorus.db")
    settings_service = SettingsService(SettingsRepository(engine))
    session_repo = SessionRepository(engine)
    msg_repo = MessageRepository(engine)
    provider_msg_repo = ProviderMessageRepository(engine)
    intent_repo = IntentStateRepository(engine)
    intent_confirmation_repo = IntentConfirmationRepository(engine)
    trace_repo = TraceRepository(engine)
    task_repo = TaskRepository(engine)
    task_artifacts_repo = TaskArtifactsRepository(engine)
    task_progress_repo = TaskProgressRepository(engine)
    task_content_repo = TaskContentRepository(engine)
    session_service = SessionService(session_repo)
    trace_service = TraceService(trace_repo)

    chat_models = ChatModelProvider(settings_service)
    # 旁路 LLM 共用固定型号:标题生成 / agent 旁白 / 记忆提取整理 / 历史摘要,不随用户当前对话设置变动
    bypass_entry = chat_models.bypass_entry()
    compact_service = CompactService(
        provider_msg_repo,
        SummaryGenerationService(bypass_entry.client, bypass_entry.model_id),
    )
    message_service = MessageService(msg_repo, provider_msg_repo, trace_service, compact_service)
    intent_state_service = IntentStateService(intent_repo, intent_confirmation_repo, session_service)
    option_repo = OptionPromptRepository(engine)
    option_service = OptionPromptService(option_repo, session_service)

    title_service = TitleGenerationService(bypass_entry.client, bypass_entry.model_id)
    aside_generator = AsideGenerator(bypass_entry.client, bypass_entry.model_id)

    memory_repo = CreatorMemoryRepository(engine)
    memory_llm = MemoryLLMService(bypass_entry.client, bypass_entry.model_id)
    memory_service = MemoryService(
        memory_repo, memory_llm, settings_service, msg_repo, task_artifacts_repo,
    )

    tool_dispatcher = build_tool_dispatch(
        settings_service, task_repo, task_content_repo, skill_loader, intent_state_service, option_service,
    )

    hooks = HookRegistry()
    trace = TraceEmitter(trace_service, tool_dispatcher)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Stop", TitlePostProcessor(session_service, message_service, title_service).on_stop, source="supervisor")
    hooks.register("Stop", MemoryExtractor(memory_service).on_stop, source="supervisor")

    agent_loop = AgentLoop(hooks, tool_dispatcher)

    task_service = TaskService(
        task_repo, task_artifacts_repo,
        task_progress_repo, task_content_repo, session_service,
        memory_service=memory_service,
    )
    supervisor_service = SupervisorService(
        session_service, message_service, hooks,
        chat_models, task_service,
        tool_dispatcher, agent_loop, intent_state_service, skill_loader,
        memory_service=memory_service,
        compact_service=compact_service,
    )
    lease_guard = LeaseGuard(task_repo, task_artifacts_repo, task_content_repo, task_progress_repo)
    subagent_service = SubAgentService(
        message_service, task_repo, task_artifacts_repo,
        task_progress_repo, task_content_repo,
        tool_dispatcher, chat_models,
        agent_loop, aside_generator, skill_loader,
        memory_service=memory_service,
        lease=lease_guard,
    )
    scheduler = TaskScheduler(
        task_repo, subagent_service.run, session_service,
        task_content_repo, task_progress_repo,
        log_dir=LOG_DIR, log_retention_days=LOG_RETENTION_DAYS,
        log_cleanup_interval=LOG_CLEANUP_INTERVAL,
    )

    app = FastAPI(
        title="Chorus",
        version="0.3.0",
        lifespan=_build_lifespan(scheduler),
    )
    app.state.session_service = session_service
    app.state.message_service = message_service
    app.state.trace_service = trace_service
    app.state.intent_state_service = intent_state_service
    app.state.option_service = option_service
    app.state.supervisor_service = supervisor_service
    app.state.task_service = task_service
    app.state.scheduler = scheduler
    app.state.settings_service = settings_service
    app.state.tool_dispatch = tool_dispatcher
    app.state.skill_loader = skill_loader
    app.state.memory_service = memory_service

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
    app.include_router(debug_router)
    app.include_router(skills_router)
    app.include_router(memory_router)
    return app


def _build_lifespan(scheduler):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        setup_logging(
            level=LOG_LEVEL, log_dir=LOG_DIR,
            max_bytes=LOG_MAX_BYTES, backup_count=LOG_BACKUP_COUNT,
        )
        run_startup(scheduler)
        yield
        scheduler.stop()
    return _lifespan


app = create_app()
