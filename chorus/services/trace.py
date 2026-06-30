"""TraceService：trace 行的应用编排（编排 TraceRepository）。

trace 横跨 message 与 task 两个概念（靠 message_id / task_id 关联），独立成 service，
不寄生在 MessageService。
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
                  source: str = "supervisor", iteration: Optional[int] = None) -> float:
        """落一条 trace 行。ts 由 service 统一打戳，调用方只给业务字段。

        返回 ts，供调用方（如 hook）给 SSE 事件复用同一时间戳，保证落库行与推送事件对齐。
        """
        ts = time.time()
        self._trace_repo.add(TraceEntry(
            id=None, session_id=session_id, message_id=message_id, task_id=task_id,
            source=source, iteration=iteration, phase=phase, ts=ts, payload=payload,
        ))
        return ts

    def list_traces(self, session_id: str) -> list[TraceEntry]:
        return self._trace_repo.list_by_session(session_id)

    def batch_aggregate(self, message_ids) -> dict:
        """批量聚合多条 message 的 trace（供 history_view 预取，避免 N+1）。"""
        return self._trace_repo.batch_aggregate(message_ids)
