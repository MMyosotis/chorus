"""轨迹表的唯一 SQL 入口。

轨迹与消息物理解耦，仅靠消息标识关联。载荷结构由领域模型强类型约束，
读回时按阶段经注册表还原成对应载荷模型，聚合逻辑重建思考与工具摘要。
"""
from __future__ import annotations

from typing import cast

from sqlalchemy import delete, select

from chorus.domain.trace import (
    MessageTrace,
    ModelRequest,
    ModelResponse,
    TraceEntry,
    TracePhase,
    TracePayload,
    TraceToolCall,
    TraceToolResult,
    aggregate_trace,
)
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.models import TraceRecord

_PAYLOAD_BY_PHASE: dict[TracePhase, type[TracePayload]] = {
    TracePhase.MODEL_REQUEST: ModelRequest,
    TracePhase.MODEL_RESPONSE: ModelResponse,
    TracePhase.TOOL_CALL: TraceToolCall,
    TracePhase.TOOL_RESULT: TraceToolResult,
}


def _to_domain(r: TraceRecord) -> TraceEntry:
    phase = TracePhase(r.phase)
    payload = _PAYLOAD_BY_PHASE[phase](**r.payload_json)
    return TraceEntry(
        id=r.id, session_id=r.session_id, message_id=r.message_id, task_id=r.task_id,
        source=r.source or "supervisor", phase=phase, created_at=r.created_at, payload=payload,
    )


def _from_domain(e: TraceEntry) -> TraceRecord:
    return TraceRecord(
        id=e.id, session_id=e.session_id, message_id=e.message_id, task_id=e.task_id,
        source=e.source, phase=e.phase.value, created_at=e.created_at,
        payload_json=e.payload.model_dump(),
    )


class TraceRepository(BaseRepository):
    @write
    def add(self, db, entry: TraceEntry) -> int:
        r = _from_domain(entry)
        db.add(r)
        db.flush()
        return r.id or 0

    @read
    def list_by_session(self, db, session_id: str) -> list[TraceEntry]:
        rs = db.scalars(
            select(TraceRecord).where(TraceRecord.session_id == session_id)
            .order_by(TraceRecord.created_at, TraceRecord.id)
        ).all()
        return [_to_domain(r) for r in rs]

    @read
    def list_by_message(self, db, message_id: str) -> list[TraceEntry]:
        rs = db.scalars(
            select(TraceRecord).where(TraceRecord.message_id == message_id)
            .order_by(TraceRecord.created_at, TraceRecord.id)
        ).all()
        return [_to_domain(r) for r in rs]

    @read
    def list_by_task(self, db, task_id: str) -> list[TraceEntry]:
        """按任务取其全部轨迹，调试单任务用。"""
        rs = db.scalars(
            select(TraceRecord).where(TraceRecord.task_id == task_id)
            .order_by(TraceRecord.created_at, TraceRecord.id)
        ).all()
        return [_to_domain(r) for r in rs]

    def aggregate_message_trace(self, message_id: str) -> MessageTrace:
        """从该消息的若干轨迹行重建思考与工具摘要。"""
        return aggregate_trace(message_id, self.list_by_message(message_id))

    @read
    def batch_aggregate(self, db, message_ids) -> dict[str, MessageTrace]:
        """一次查询批量聚合多条消息的轨迹，避免逐条查询。无轨迹的消息不在结果中。"""
        ids = list(message_ids)
        if not ids:
            return {}
        rs = db.scalars(
            select(TraceRecord).where(TraceRecord.message_id.in_(ids))
            .order_by(TraceRecord.created_at, TraceRecord.id)
        ).all()
        grouped: dict[str, list[TraceEntry]] = {}
        for r in rs:
            entry = _to_domain(r)
            mid = cast(str, entry.message_id)
            grouped.setdefault(mid, []).append(entry)
        return {mid: aggregate_trace(mid, entries) for mid, entries in grouped.items()}

    @write
    def delete_by_session(self, db, session_id: str) -> None:
        db.execute(delete(TraceRecord).where(TraceRecord.session_id == session_id))

    @write
    def delete_by_message(self, db, message_id: str) -> None:
        db.execute(delete(TraceRecord).where(TraceRecord.message_id == message_id))
