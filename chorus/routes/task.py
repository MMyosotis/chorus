# kitty/routes/task.py
"""task 资源路由：任务图查询 + HIL 写操作（confirm/retry/cancel）+ ReAct 过程。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chorus.routes.providers import provide_session_service, provide_task_service
from chorus.services.session import SessionService
from chorus.services.task import ConflictError, TaskService

router = APIRouter(prefix="/api")


class ConfirmRequest(BaseModel):
    selected: Optional[int] = None


class RetryRequest(BaseModel):
    feedback: dict


@router.get("/tasks")
def get_task_graph(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    task: TaskService = Depends(provide_task_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return task.get_graph(session_id)


@router.get("/tasks/{task_id}/steps")
def get_task_steps(
    task_id: str,
    task: TaskService = Depends(provide_task_service),
):
    try:
        return {"steps": task.get_steps(task_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")


@router.get("/tasks/{task_id}/activities")
def get_task_activities(
    task_id: str,
    limit: int = 50,
    after_seq: Optional[int] = None,
    task: TaskService = Depends(provide_task_service),
):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit 须在 1..100")
    if after_seq is not None and after_seq < 0:
        raise HTTPException(status_code=422, detail="after_seq 不可为负")
    try:
        return {
            "task_id": task_id,
            "activities": task.get_activities(task_id, limit=limit, after_seq=after_seq),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")


@router.post("/tasks/{task_id}/confirm")
def confirm_task(
    task_id: str,
    req: ConfirmRequest,
    task: TaskService = Depends(provide_task_service),
):
    try:
        return task.confirm(task_id, req.selected)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/tasks/{task_id}/retry")
def retry_task(
    task_id: str,
    req: RetryRequest,
    task: TaskService = Depends(provide_task_service),
):
    try:
        return task.retry(task_id, req.feedback)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/sessions/{session_id}/pipeline:cancel")
def cancel_pipeline(
    session_id: str,
    session: SessionService = Depends(provide_session_service),
    task: TaskService = Depends(provide_task_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    try:
        return task.cancel_pipeline(session_id)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
