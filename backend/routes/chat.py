import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.chat import chat_stream, get_history, reset_history

router = APIRouter(prefix="/api/chat")


class ChatRequest(BaseModel):
    message: str


@router.post("")
def chat_endpoint(req: ChatRequest):
    """SSE 流式聊天"""
    def event_generator():
        try:
            for token in chat_stream(req.message):
                data = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
def history_endpoint():
    return {"messages": get_history()}


@router.post("/reset")
def reset_endpoint():
    reset_history()
    return {"status": "ok"}
