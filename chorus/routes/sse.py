"""路由层 SSE 序列化与流式响应包装。"""
from __future__ import annotations

import json
from typing import Iterable

from fastapi.responses import StreamingResponse

_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


def sse(event) -> str:
    """把事件序列化成一行 SSE 数据帧。"""
    return f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"


def sse_stream(generator: Iterable[str]) -> StreamingResponse:
    """把已序列化的数据帧流包成事件流响应。"""
    return StreamingResponse(generator, media_type="text/event-stream", headers=_SSE_HEADERS)
