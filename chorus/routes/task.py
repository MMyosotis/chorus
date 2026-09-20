"""任务资源路由：人工确认写操作。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.domain.task import ValidationError
from chorus.routes.providers import provide_session_service, provide_task_service
from chorus.services.session import SessionService
from chorus.services.task import TaskService

router = APIRouter(prefix="/api")


class ConfirmRequest(BaseModel):
    selected: Optional[int] = None


class RetryRequest(BaseModel):
    feedback: str


class EditRequest(BaseModel):
    markdown: Optional[str] = None
    candidates: Optional[list[dict]] = None


@router.post("/tasks/{task_id}/confirm")
def confirm_task(
    task_id: str,
    req: ConfirmRequest,
    task: TaskService = Depends(provide_task_service),
):
    return task.confirm(task_id, req.selected)


@router.post("/tasks/{task_id}/retry")
def retry_task(
    task_id: str,
    req: RetryRequest,
    task: TaskService = Depends(provide_task_service),
):
    return task.retry(task_id, req.feedback)


@router.post("/tasks/{task_id}/edit")
def edit_task(
    task_id: str,
    req: EditRequest,
    task: TaskService = Depends(provide_task_service),
):
    payload = {"markdown": req.markdown, "candidates": req.candidates}
    try:
        return task.edit(task_id, payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.correction) from e


@router.post("/sessions/{session_id}/pipeline:cancel")
def cancel_pipeline(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    task: TaskService = Depends(provide_task_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return task.cancel_pipeline(session_id)
