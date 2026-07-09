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
    return {"sessions": [summary.model_dump() for summary in session.list()]}


@router.post("")
def create_session(req: CreateRequest, session: SessionService = Depends(provide_session_service)):
    title = (req.title or "新对话").strip() or "新对话"
    if len(title) > 60:
        raise HTTPException(status_code=422, detail="title 长度不能超过 60")
    created = session.create(title)
    return {"id": created.id, "title": created.title, "created_at": created.created_at, "updated_at": created.updated_at}


@router.delete("/{session_id}")
def delete_session(session_id: str, session: SessionService = Depends(provide_session_service)):
    session.delete(session_id)  # 幂等：删 0 行也返 ok
    return {"status": "ok"}


@router.patch("/{session_id}")
def rename_session(session_id: str, req: RenameRequest, session: SessionService = Depends(provide_session_service)):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    try:
        renamed = session.rename(session_id, req.title)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": renamed.id, "title": renamed.title, "created_at": renamed.created_at, "updated_at": renamed.updated_at}


@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    message: MessageService = Depends(provide_message_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"messages": [_view_to_dict(view) for view in message.history_view(session_id)]}


@router.get("/{session_id}/traces")
def get_traces(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    trace: TraceService = Depends(provide_trace_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"traces": [_trace_to_dict(entry) for entry in trace.list_traces(session_id)]}


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
    message: MessageService = Depends(provide_message_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    current = intent.get(session_id)
    if current.intent_status != "ready_to_confirm":
        raise HTTPException(status_code=409, detail="intent is not ready to confirm")
    state = intent.confirm(session_id)
    message.rewrite_last_tool_result(
        session_id, "update_intent_state",
        "用户已同意，意图进入 confirmed，等待建图",
    )

    def event_generator():
        yield _sse(IntentStateEvent(state=state.public_dict()))
        for event in supervisor.stream(session_id, "确认并开始"):
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
    message: MessageService = Depends(provide_message_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    state = intent.reopen(session_id)
    message.rewrite_last_tool_result(
        session_id, "update_intent_state",
        "用户要求继续调整，意图回到 needs_clarification",
    )

    def event_generator():
        yield _sse(IntentStateEvent(state=state.public_dict()))
        for event in supervisor.stream(session_id, "用户希望继续调整方案"):
            yield _sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/resume")
def resume_session(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    def event_generator():
        for event in supervisor.resume(session_id):
            yield _sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _view_to_dict(view: MessageView) -> dict:
    item: dict = {"role": view.role, "content": view.content}
    if view.role == "assistant":
        item["thinking"] = [seg.model_dump() for seg in view.thinking]
        item["tools"] = [tool.model_dump() for tool in view.tools]
    return item


def _trace_to_dict(entry: TraceEntry) -> dict:
    return {
        "type": "trace",
        "phase": entry.phase.value,
        "message_id": entry.message_id,
        "task_id": entry.task_id,
        "source": entry.source,
        "created_at": entry.created_at,
        "payload": entry.payload.model_dump(),
    }


def _sse(event) -> str:
    return f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
