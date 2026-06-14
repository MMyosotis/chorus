from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.chat import client as openai_client, init_chat
from backend.config import (
    CONV_MAX_BYTES,
    CONV_MAX_COUNT,
    CONV_TTL_DAYS,
    CONVERSATIONS_DIR,
    SKILLS_DIR,
    set_image_test_mode,
)
from backend.conversations.store import ConversationStore
from backend.hooks import HookManager
from backend.hooks.builtin import register_builtin_hooks
from backend.routes.chat import init_routes
from backend.routes.chat import router as chat_router
from backend.routes.debug import router as debug_router
from backend.settings import init_settings_store
from backend.skills import init_skill_loader


def create_app() -> FastAPI:
    app = FastAPI(title="Little Kitty", version="0.1.0")

    # 初始化 skill 系统
    init_skill_loader(SKILLS_DIR)

    # 初始化通用 KV 配置存储（独立于会话数据库）
    settings_store = init_settings_store(CONVERSATIONS_DIR.parent / "settings.db")
    # 把持久化的配置回灌到 config 内存
    set_image_test_mode(bool(settings_store.get("image_test_mode", False)))

    # 初始化会话存储
    store = ConversationStore(
        CONVERSATIONS_DIR,
        ttl_days=CONV_TTL_DAYS,
        max_bytes=CONV_MAX_BYTES,
        max_count=CONV_MAX_COUNT,
    )
    store.load_all()

    # 初始化 hook 系统并注册内置 hook
    hooks = HookManager()
    register_builtin_hooks(hooks, openai_client)

    init_chat(store, hooks)
    init_routes(store)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    app.include_router(debug_router)
    return app


app = create_app()
