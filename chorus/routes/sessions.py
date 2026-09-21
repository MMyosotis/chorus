"""会话增删改查、轨迹与会话视图、续跑入口路由。"""

from __future__ import annotations

from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.domain.bypass import BypassScope
from chorus.domain.events import IntentStateEvent, TraceEvent
from chorus.domain.intent import IntentStateView
from chorus.domain.trace import TraceEntry
from chorus.domain.suggestion import SuggestionGenerationService
from chorus.routes.providers import (
    provide_intent_state_service,
    provide_message_service,
    provide_option_service,
    provide_session_service,
    provide_session_view_service,
    provide_suggestion_service,
    provide_supervisor_service,
    provide_tool_dispatch,
    provide_trace_service,
)
from chorus.routes.sse import sse, sse_stream
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.services.session_view import SessionViewService
from chorus.services.trace import TraceService
from chorus.tools import ToolDispatch

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


@router.get("/{session_id}/traces")
def get_traces(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    trace: TraceService = Depends(provide_trace_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"traces": [_trace_to_dict(entry) for entry in trace.list_traces(session_id)]}


@router.post("/{session_id}/suggestions")
def suggest_input(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
    message: MessageService = Depends(provide_message_service),
    suggestion: SuggestionGenerationService = Depends(provide_suggestion_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    state = intent.get(session_id)
    return {"suggestions": suggestion.generate(state, message.list_messages(session_id), BypassScope(session_id=session_id))}


def _resume_with_tool(
    session_id: str,
    tool_name: str,
    signal: str,
    intent: IntentStateService,
    supervisor: SupervisorService,
    tools: ToolDispatch,
) -> Iterator[str]:
    """外部信号解开挂起的工具：让工具翻状态拿回执文案，再续跑 loop。"""
    result_text = tools.get_tool(tool_name).resolve_external(session_id, signal)
    yield sse(IntentStateEvent(state=IntentStateView.from_state(intent.get(session_id))))
    for event in supervisor.resume(session_id, tool_name, result_text):
        yield sse(event)


@router.post("/{session_id}/intent:confirm")
def confirm_intent(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    tools: ToolDispatch = Depends(provide_tool_dispatch),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    if intent.get(session_id).intent_status != "ready_to_confirm":
        raise HTTPException(status_code=409, detail="intent is not ready to confirm")
    return sse_stream(_resume_with_tool(session_id, "update_intent_state", "confirm", intent, supervisor, tools))


@router.post("/{session_id}/intent:reopen")
def reopen_intent(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    tools: ToolDispatch = Depends(provide_tool_dispatch),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return sse_stream(_resume_with_tool(session_id, "update_intent_state", "reopen", intent, supervisor, tools))


@router.post("/{session_id}/resume")
def resume_session(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    tools: ToolDispatch = Depends(provide_tool_dispatch),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    # 收尾锁：先验确有未回执的建图挂起再放行，挡重复按铃
    if not supervisor.has_unreceipted_plan(session_id):
        raise HTTPException(status_code=409, detail="no unreceipted plan to resume")
    return sse_stream(_resume_with_tool(session_id, "create_plan", "finish", intent, supervisor, tools))


@router.get("/{session_id}/view")
def get_session_view(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    view: SessionViewService = Depends(provide_session_view_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return view.collect(session_id)


class OptionChooseAnswerRequest(BaseModel):
    signal: str
    custom_text: Optional[str] = None


class OptionChooseRequest(BaseModel):
    answers: list[OptionChooseAnswerRequest]


def _resume_option(
    session_id: str,
    req: OptionChooseRequest,
    supervisor: SupervisorService,
    tools: ToolDispatch,
) -> Iterator[str]:
    result_text = tools.get_tool("present_options").resolve_external(
        session_id,
        "submit",
        {"answers": [answer.model_dump(exclude_none=True) for answer in req.answers]},
    )
    for event in supervisor.resume(session_id, "present_options", result_text):
        yield sse(event)


@router.post("/{session_id}/option:choose")
def choose_option(
    session_id: str,
    req: OptionChooseRequest,
    session: SessionService = Depends(provide_session_service),
    option: OptionPromptService = Depends(provide_option_service),
    supervisor: SupervisorService = Depends(provide_supervisor_service),
    tools: ToolDispatch = Depends(provide_tool_dispatch),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    open_prompt = option.get_open(session_id)
    if open_prompt is None:
        raise HTTPException(status_code=409, detail="option prompt not open")
    return sse_stream(_resume_option(session_id, req, supervisor, tools))


def _trace_to_dict(entry: TraceEntry) -> dict:
    return TraceEvent(
        phase=entry.phase, message_id=entry.message_id,
        task_id=entry.task_id, source=entry.source,
        created_at=entry.created_at, payload=entry.payload,
    ).model_dump(mode="json")
