"""流式聊天路由。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.routes.providers import (
    provide_session_service,
    provide_supervisor_service,
)
from chorus.services.session import SessionService

router = APIRouter(prefix="/api/sessions")


class ChatRequest(BaseModel):
    message: str


@router.post("/{session_id}/chat")
def chat_endpoint(
    session_id: str,
    req: ChatRequest,
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    session: SessionService = Depends(provide_session_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    def event_generator():
        for event in supervisor.stream(session_id, req.message):
            yield f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
