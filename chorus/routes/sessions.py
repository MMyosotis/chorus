"""会话增删改查与消息、轨迹视图路由。"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.domain.events import IntentStateEvent
from chorus.domain.message import MessageView
from chorus.domain.trace import TraceEntry
from chorus.routes.providers import (
    provide_intent_state_service,
    provide_message_service,
    provide_session_service,
    provide_supervisor_service,
    provide_trace_service,
)
from chorus.services.intent_state import IntentStateService
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
    session.delete(session_id)  # 幂等：删 0 行也返 ok
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


@router.get("/{session_id}/intent-state")
def get_intent_state(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"state": intent.get(session_id).public_dict()}


@router.post("/{session_id}/intent:confirm")
def confirm_intent(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    current = intent.get(session_id)
    if current.intent_status != "ready_to_confirm":
        raise HTTPException(status_code=409, detail="intent is not ready to confirm")
    state = intent.confirm(session_id)

    def event_generator():
        yield _sse(IntentStateEvent(state=state.public_dict()))
        for event in supervisor.stream(session_id, "确认并开始", require_create_plan=True):
            yield _sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/intent:reopen")
def reopen_intent(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"state": intent.reopen(session_id).public_dict()}


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


def _sse(event) -> str:
    return f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
