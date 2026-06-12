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
    """SSE 流式聊天（含工具调用支持）。"""

    def event_generator():
        for event in chat_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

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
