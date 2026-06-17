"""FastAPI 应用工厂：用 AppContainer 装配，路由经 Depends 取 Service。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kitty.container import AppContainer
from kitty.routes.chat import router as chat_router
from kitty.routes.sessions import router as sessions_router
from kitty.routes.settings import router as settings_router


def create_app() -> FastAPI:
    app = FastAPI(title="Little Kitty", version="0.2.0")

    container = AppContainer()
    container.startup()
    app.state.container = container

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
