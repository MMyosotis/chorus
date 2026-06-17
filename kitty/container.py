"""AppContainer：单点装配所有 Repository / Service / Tool / Hook / ChatService。

替代 create_app 内联装配：构造一次，挂到 app.state.container；
routes 经 Depends（routes/providers.py）从这里取 service。所有依赖在 __init__ 显式注入，
无模块级单例。startup() 跑一次性的 load / cleanup。
"""

from __future__ import annotations

from pathlib import Path

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
    SYSTEM_PROMPT,
)
from kitty.hooks.manager import HookManager
from kitty.hooks.registry import build_hooks
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.session import SessionRepository
from kitty.repositories.message import MessageRepository
from kitty.repositories.settings import SettingsRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.chat import ChatService
from kitty.services.cleanup import CleanupService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService
from kitty.services.skill import SkillService
from kitty.services.system_prompt_builder import SystemPromptBuilder
from kitty.services.title import TitleGenerationService
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


class AppContainer:
    def __init__(self) -> None:
        # Skill
        self.skill_service = SkillService(SKILLS_DIR)

        # Settings（独立 db 文件）
        self.settings_conn = ConnectionFactory(DATA_DIR / "settings.db")
        self.settings_repo = SettingsRepository(self.settings_conn)
        self.settings_service = SettingsService(self.settings_repo)

        # Repository（会话 db）
        self.conn = ConnectionFactory(DATA_DIR / "little-kitty.db")
        self.session_repo = SessionRepository(self.conn)
        self.msg_repo = MessageRepository(self.conn)
        self.trace_repo = TraceRepository(self.conn)

        # Service
        self.cleanup_service = CleanupService(
            self.session_repo, self.msg_repo, CONV_TTL_DAYS, CONV_MAX_BYTES, CONV_MAX_COUNT
        )
        self.session_service = SessionService(
            self.session_repo, self.msg_repo, self.trace_repo, self.cleanup_service
        )
        self.system_prompt_builder = SystemPromptBuilder(SYSTEM_PROMPT, self.skill_service)
        self.openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.title_service = TitleGenerationService(self.openai_client, MODEL_ID)

        # Tools
        self.workspace_policy = WorkspacePolicy(Path.cwd())
        self.ark_client = ArkImageClient(ARK_IMAGE_API_KEY, ARK_IMAGE_BASE_URL, ARK_IMAGE_MODELS)
        self.baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
        self.tool_registry = ToolRegistry([
            BashTool(),
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            GlobSearchTool(),
            LoadSkillTool(),
            GenerateImageTool(
                self.settings_service.get_image_test_mode, IMAGE_TEST_FAKE_URL, self.ark_client
            ),
            BaiduSearchTool(self.baidu_client),
        ])
        self.tool_ctx_factory: ToolCtxFactory = self._tool_ctx_factory

        # Hook + ChatService
        self.hooks = HookManager(build_hooks(
            self.session_service, self.system_prompt_builder, self.title_service,
            MODEL_ID, MAX_TOKENS, self.tool_registry, self.tool_ctx_factory,
        ))
        self.chat_service = ChatService(
            self.session_service, self.hooks, self.openai_client,
            MODEL_ID, MAX_TOKENS, MAX_TOOL_ITERATIONS, self.tool_registry.schemas_openai(),
        )

    def startup(self) -> None:
        self.skill_service.load()
        self.settings_service.load_all()
        self.session_service.load()

    def _tool_ctx_factory(self, session_id: str | None) -> ToolContext:
        return ToolContext(
            workspace=self.workspace_policy,
            skill_service=self.skill_service,
            session_id=session_id,
        )
