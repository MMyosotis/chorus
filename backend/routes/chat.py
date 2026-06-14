import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.chat import chat_stream
from backend.conversations.store import ConversationStore

router = APIRouter(prefix="/api/conversations")

_store: Optional[ConversationStore] = None


def init_routes(store: ConversationStore) -> None:
    global _store
    _store = store


def _require_store() -> ConversationStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="store not initialized")
    return _store


class CreateRequest(BaseModel):
    title: Optional[str] = None


class RenameRequest(BaseModel):
    title: str = Field(...)


class ChatRequest(BaseModel):
    message: str


@router.get("")
def list_conversations():
    store = _require_store()
    return {"conversations": store.list_meta()}


@router.post("")
def create_conversation(req: CreateRequest):
    store = _require_store()
    title = (req.title or "新对话").strip() or "新对话"
    if len(title) > 60:
        raise HTTPException(status_code=422, detail="title 长度不能超过 60")
    return store.create(title)


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str):
    store = _require_store()
    try:
        store.delete(conv_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"status": "ok"}


@router.patch("/{conv_id}")
def rename_conversation(conv_id: str, req: RenameRequest):
    store = _require_store()
    if not store.has(conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    try:
        return store.rename(conv_id, req.title)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{conv_id}/messages")
def get_messages(conv_id: str):
    store = _require_store()
    if not store.has(conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"messages": store.get_history_view(conv_id)}


@router.get("/{conv_id}/traces")
def get_traces(conv_id: str):
    store = _require_store()
    try:
        return {"traces": store.list_traces(conv_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="conversation not found")


@router.post("/{conv_id}/chat")
def chat_endpoint(conv_id: str, req: ChatRequest):
    """SSE 流式聊天（含工具调用支持）。"""
    store = _require_store()
    if not store.has(conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")

    lock = store.get_lock(conv_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="conversation is busy")

    def event_generator():
        released = False
        def _release():
            nonlocal released
            if not released:
                released = True
                lock.release()
        try:
            for event in chat_stream(req.message, conv_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                # done / error 之后的事件（如 title_update）不再持有会话锁，
                # 避免同会话第二条消息因 _maybe_generate_title 阻塞而 409
                if event.get("type") in ("done", "error"):
                    _release()
        finally:
            _release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
