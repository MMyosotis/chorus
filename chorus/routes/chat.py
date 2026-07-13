"""流式聊天路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.routes.providers import (
    provide_session_service,
    provide_supervisor_service,
)
from chorus.routes.sse import sse, sse_stream
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
            yield sse(event)

    return sse_stream(event_generator())
