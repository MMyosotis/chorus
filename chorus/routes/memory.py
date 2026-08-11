"""创作者记忆管理路由：列表/新增/编辑/删除 HTTP 适配。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from chorus.domain.memory.models import Kind
from chorus.routes.providers import provide_memory_service
from chorus.services.memory import MemoryService

router = APIRouter(prefix="/api/memory")


class MemoryView(BaseModel):
    id: str
    kind: Kind
    description: str
    content: str
    platform: list[str]
    visible_to: list[str]
    created_at: float


class CreateRequest(BaseModel):
    description: str
    content: str
    platform: list[str] = Field(default_factory=list)
    visible_to: list[str] = Field(default_factory=list)
    kind: Kind = "reference"


class UpdateRequest(BaseModel):
    description: str
    content: str
    platform: list[str]
    visible_to: list[str]
    kind: Kind


def _to_view(memory) -> MemoryView:
    return MemoryView(**memory.model_dump())


@router.get("")
def list_memories(memory: MemoryService = Depends(provide_memory_service)):
    return {"memories": [_to_view(item) for item in memory.list_all()]}


@router.post("")
def create_memory(req: CreateRequest, memory: MemoryService = Depends(provide_memory_service)):
    created = memory.create_memory(
        req.description, req.content, req.platform, req.visible_to, req.kind,
    )
    return _to_view(created)


@router.put("/{memory_id}")
def put_memory(
    memory_id: str,
    req: UpdateRequest,
    memory: MemoryService = Depends(provide_memory_service),
):
    updated = memory.update_memory(
        memory_id,
        req.description, req.content,
        req.platform, req.visible_to, req.kind,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _to_view(updated)


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, memory: MemoryService = Depends(provide_memory_service)):
    memory.delete_memory(memory_id)  # 幂等：删 0 行也返 ok
    return {"id": memory_id}
