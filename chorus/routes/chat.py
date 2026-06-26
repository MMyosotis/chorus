"""SSE 流式聊天路由（Depends 注入 SupervisorService + SessionService）。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.routes.providers import (
    provide_session_service,
    provide_settings_service,
    provide_supervisor_service,
)
from chorus.services.session import SessionService
from chorus.services.settings import SettingsService

router = APIRouter(prefix="/api/sessions")


class ChatRequest(BaseModel):
    message: str


@router.post("/{session_id}/chat")
def chat_endpoint(
    session_id: str,
    req: ChatRequest,
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    session: SessionService = Depends(provide_session_service),
    settings: SettingsService = Depends(provide_settings_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    lock = session.get_lock(session_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="session is busy")

    image_model = settings.get_image_model()
    web_search = settings.get_web_search()

    def event_generator():
        released = False

        def _release():
            nonlocal released
            if not released:
                released = True
                lock.release()

        try:
            for event in supervisor.stream(
                session_id, req.message,
                image_model=image_model, web_search=web_search,
            ):
                yield f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                if event.type in ("done", "error"):
                    _release()
        finally:
            _release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
