from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import SKILLS_DIR
from backend.routes.chat import router as chat_router
from backend.skills import init_skill_loader


def create_app() -> FastAPI:
    app = FastAPI(title="Little Kitty", version="0.1.0")

    # 初始化 skill 系统
    init_skill_loader(SKILLS_DIR)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    return app


app = create_app()
