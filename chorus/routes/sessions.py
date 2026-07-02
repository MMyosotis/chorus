"""会话增删改查与消息、轨迹视图路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.domain.message import MessageView
from chorus.domain.trace import TraceEntry
from chorus.routes.providers import (
    provide_message_service,
    provide_session_service,
    provide_trace_service,
)
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService

router = APIRouter(prefix="/api/sessions")


class CreateRequest(BaseModel):
    title: Optional[str] = None


class RenameRequest(BaseModel):
    title: str


@router.get("")
def list_sessions(session: SessionService = Depends(provide_session_service)):
    return {"sessions": [s.model_dump() for s in session.list()]}


@router.post("")
def create_session(req: CreateRequest, session: SessionService = Depends(provide_session_service)):
    title = (req.title or "新对话").strip() or "新对话"
    if len(title) > 60:
        raise HTTPException(status_code=422, detail="title 长度不能超过 60")
    c = session.create(title)
    return {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}


@router.delete("/{session_id}")
def delete_session(session_id: str, session: SessionService = Depends(provide_session_service)):
    try:
        session.delete(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok"}


@router.patch("/{session_id}")
def rename_session(session_id: str, req: RenameRequest, session: SessionService = Depends(provide_session_service)):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    try:
        c = session.rename(session_id, req.title)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}


@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    message: MessageService = Depends(provide_message_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"messages": [_view_to_dict(v) for v in message.history_view(session_id)]}


@router.get("/{session_id}/traces")
def get_traces(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    trace: TraceService = Depends(provide_trace_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"traces": [_trace_to_dict(t) for t in trace.list_traces(session_id)]}


def _view_to_dict(v: MessageView) -> dict:
    item: dict = {"role": v.role, "content": v.content}
    if v.role == "assistant":
        item["thinking"] = [s.model_dump() for s in v.thinking]
        item["tools"] = [t.model_dump() for t in v.tools]
    return item


def _trace_to_dict(t: TraceEntry) -> dict:
    return {
        "type": "trace",
        "phase": t.phase.value,
        "message_id": t.message_id,
        "task_id": t.task_id,
        "source": t.source,
        "created_at": t.created_at,
        "payload": t.payload.model_dump(),
    }
