from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.chat import init_chat_store
from backend.config import (
    CONV_MAX_BYTES,
    CONV_MAX_COUNT,
    CONV_TTL_DAYS,
    CONVERSATIONS_DIR,
    SKILLS_DIR,
)
from backend.conversations.store import ConversationStore
from backend.routes.chat import init_routes
from backend.routes.chat import router as chat_router
from backend.skills import init_skill_loader


def create_app() -> FastAPI:
    app = FastAPI(title="Little Kitty", version="0.1.0")

    # 初始化 skill 系统
    init_skill_loader(SKILLS_DIR)

    # 初始化会话存储
    store = ConversationStore(
        CONVERSATIONS_DIR,
        ttl_days=CONV_TTL_DAYS,
        max_bytes=CONV_MAX_BYTES,
        max_count=CONV_MAX_COUNT,
    )
    store.load_all()
    init_chat_store(store)
    init_routes(store)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    return app


app = create_app()
