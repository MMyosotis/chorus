"""轨迹服务：轨迹行的应用编排。

轨迹横跨消息与任务两个概念，独立成服务，不寄生在消息服务。
"""

from __future__ import annotations

import time
from typing import Optional

from chorus.domain.trace import TraceEntry, TracePhase
from chorus.repo.trace import TraceRepository


class TraceService:
    def __init__(self, trace_repo: TraceRepository):
        self._trace_repo = trace_repo

    def add_trace(self, *, session_id: str, phase: TracePhase, payload: dict,
                  message_id: Optional[str] = None, task_id: Optional[str] = None,
                  source: str = "supervisor") -> float:
        """落一条轨迹行，时间由本层打戳。返回时间戳供调用方事件复用以对齐。"""
        ts = time.time()
        self._trace_repo.add(TraceEntry(
            id=None, session_id=session_id, message_id=message_id, task_id=task_id,
            source=source, phase=phase, ts=ts, payload=payload,
        ))
        return ts

    def list_traces(self, session_id: str) -> list[TraceEntry]:
        return self._trace_repo.list_by_session(session_id)

    def batch_aggregate(self, message_ids) -> dict:
        """批量聚合多条消息的轨迹，避免逐条查询。"""
        return self._trace_repo.batch_aggregate(message_ids)
