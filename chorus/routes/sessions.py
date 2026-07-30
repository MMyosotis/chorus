"""会话增删改查与消息、轨迹视图路由。"""

from __future__ import annotations

from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.agents.supervisor import SupervisorService
from chorus.domain.events import IntentStateEvent
from chorus.domain.intent import IntentConfirmation
from chorus.domain.message import MessageView
from chorus.domain.option import OptionPrompt
from chorus.domain.trace import TraceEntry
from chorus.routes.providers import (
    provide_intent_state_service,
    provide_message_service,
    provide_option_service,
    provide_session_service,
    provide_supervisor_service,
    provide_tool_dispatch,
    provide_trace_service,
)
from chorus.routes.sse import sse, sse_stream
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
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
    return {"state": intent.get(session_id).model_dump(mode="json")}


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
    yield sse(IntentStateEvent(state=intent.get(session_id).model_dump(mode="json")))
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
    return sse_stream(_resume_with_tool(session_id, "create_plan", "finish", intent, supervisor, tools))


class OptionChooseRequest(BaseModel):
    signal: str
    custom_text: Optional[str] = None


def _resume_option(
    session_id: str,
    req: OptionChooseRequest,
    supervisor: SupervisorService,
    tools: ToolDispatch,
) -> Iterator[str]:
    payload = {"custom_text": req.custom_text} if req.custom_text else None
    result_text = tools.get_tool("present_options").resolve_external(
        session_id, req.signal, payload,
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


@router.get("/{session_id}/options")
def list_option_prompts(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    option: OptionPromptService = Depends(provide_option_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"prompts": [_option_prompt_to_dict(prompt) for prompt in option.list_by_session(session_id)]}


@router.get("/{session_id}/intent-confirmations")
def list_intent_confirmations(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    intent: IntentStateService = Depends(provide_intent_state_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"confirmations": [_confirmation_to_dict(confirmation) for confirmation in intent.list_confirmations(session_id)]}


def _option_prompt_to_dict(prompt: OptionPrompt) -> dict:
    return {
        "prompt_id": prompt.prompt_id,
        "message_id": prompt.message_id,
        "question": prompt.question,
        "options": [item.model_dump() for item in prompt.options],
        "allow_custom": prompt.allow_custom,
        "status": prompt.status,
        "answer": prompt.answer.model_dump(exclude_none=True) if prompt.answer else None,
        "created_at": prompt.created_at,
    }


def _confirmation_to_dict(confirmation: IntentConfirmation) -> dict:
    return confirmation.model_dump(mode="json", exclude={"session_id"}, exclude_none=True)


def _view_to_dict(view: MessageView) -> dict:
    item: dict = {"id": view.id, "role": view.role, "content": view.content}
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
