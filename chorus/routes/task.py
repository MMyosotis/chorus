"""任务资源路由：任务图查询与人工确认写操作。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.routes.providers import provide_session_service, provide_task_service
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.domain.task import dump_task_graph

router = APIRouter(prefix="/api")


class ConfirmRequest(BaseModel):
    selected: Optional[int] = None


class RetryRequest(BaseModel):
    feedback: str


@router.get("/tasks")
def get_task_graph(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    task: TaskService = Depends(provide_task_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return dump_task_graph(task.get_graph(session_id))


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


@router.post("/sessions/{session_id}/pipeline:cancel")
def cancel_pipeline(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    task: TaskService = Depends(provide_task_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return task.cancel_pipeline(session_id)
