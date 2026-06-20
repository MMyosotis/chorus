"""SSE 流式聊天路由（Depends 注入 ChatService + SessionService）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from kitty.routes.providers import (
    provide_chat_service,
    provide_session_service,
    provide_settings_service,
)
from kitty.services.chat import ChatService
from kitty.services.session import SessionService
from kitty.services.settings import SettingsService

router = APIRouter(prefix="/api/sessions")


class ChatRequest(BaseModel):
    message: str


@router.post("/{session_id}/chat")
def chat_endpoint(
    session_id: str,
    req: ChatRequest,
    chat: ChatService = Depends(provide_chat_service),
    session: SessionService = Depends(provide_session_service),
    settings: SettingsService = Depends(provide_settings_service),
):
    if not session.exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    lock = session.get_lock(session_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="session is busy")

    # 进程级模型选项：每次请求按当前设置应用（对话模型 / 生图模型 / 联网搜索）
    chat_model = settings.get_chat_model()
    image_model = settings.get_image_model()
    web_search = settings.get_web_search()

    def event_generator():
        released = False

        def _release():
            nonlocal released
            if not released:
                released = True
                lock.release()

        try:
            for event in chat.stream(
                session_id, req.message,
                model=chat_model, image_model=image_model, web_search=web_search,
            ):
                yield f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                # done / error 之后的事件（如 title_update）不再持有会话锁
                if event.type in ("done", "error"):
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
