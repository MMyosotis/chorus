"""轨迹服务：轨迹行的应用编排。

轨迹横跨消息与任务两个概念，独立成服务，不寄生在消息服务。
"""

from __future__ import annotations

import time
from typing import Optional

from chorus.domain.trace import TraceEntry, TracePhase, TracePayload
from chorus.repo.trace import TraceRepository


class TraceService:
    def __init__(self, trace_repo: TraceRepository):
        self._trace_repo = trace_repo

    def add_trace(
            self, *, session_id: str, phase: TracePhase, payload: TracePayload,
            message_id: Optional[str] = None, task_id: Optional[str] = None, source: str = "supervisor",
            created_at: Optional[float] = None,
    ) -> float:
        """落一条轨迹行，可复用业务事件时间。"""
        trace_time = created_at if created_at is not None else time.time()
        self._trace_repo.add(TraceEntry(
            id=None, session_id=session_id, message_id=message_id, task_id=task_id,
            source=source, phase=phase, created_at=trace_time, payload=payload,
        ))
        return trace_time

    def add_entry(self, entry: TraceEntry) -> None:
        """落一条调用方已组装完的轨迹行,时间戳由调用方打。"""
        self._trace_repo.add(entry)

    def list_traces(self, session_id: str) -> list[TraceEntry]:
        return self._trace_repo.list_by_session(session_id)

    def batch_aggregate(self, message_ids) -> dict:
        """批量聚合多条消息的轨迹，避免逐条查询。"""
        return self._trace_repo.batch_aggregate(message_ids)
