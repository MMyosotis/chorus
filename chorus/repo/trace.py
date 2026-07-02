"""轨迹表的唯一 SQL 入口。

轨迹与消息物理解耦，仅靠消息标识关联。各阶段载荷结构由写入方约定、聚合方依赖。
映射归框架，转换集中在行模型，聚合逻辑重建思考与工具摘要。
"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.trace import (
    MessageTrace,
    ThinkingSegment,
    ToolInvocation,
    TraceEntry,
    TracePhase,
)
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_id      TEXT,
    task_id         TEXT,
    source          TEXT NOT NULL DEFAULT 'supervisor',
    phase           TEXT NOT NULL,
    created_at      REAL NOT NULL,
    payload_json    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_traces_session_created_at ON traces(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_traces_message ON traces(message_id);
CREATE INDEX IF NOT EXISTS idx_traces_task ON traces(task_id, created_at);
"""


class TraceRow(BaseModel):
    """轨迹表持久化形状，与列一一对应。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: Optional[int] = None
    session_id: str
    message_id: Optional[str] = None
    task_id: Optional[str] = None
    source: str = "supervisor"
    phase: str
    created_at: float
    payload_json: str

    def to_domain(self) -> TraceEntry:
        try:
            payload = json.loads(self.payload_json) if self.payload_json else {}
        except json.JSONDecodeError:
            payload = {}
        return TraceEntry(
            id=self.id,
            session_id=self.session_id,
            message_id=self.message_id,
            task_id=self.task_id,
            source=self.source or "supervisor",
            phase=TracePhase(self.phase),
            created_at=self.created_at,
            payload=payload,
        )

    @classmethod
    def from_domain(cls, entry: TraceEntry) -> "TraceRow":
        return cls(
            id=entry.id,
            session_id=entry.session_id,
            message_id=entry.message_id,
            task_id=entry.task_id,
            source=entry.source,
            phase=entry.phase.value,
            created_at=entry.created_at,
            payload_json=json.dumps(entry.payload, ensure_ascii=False),
        )


_COLS = ", ".join(TraceRow.model_fields)
_PH = ", ".join(f":{k}" for k in TraceRow.model_fields)


class TraceRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def add(self, entry: TraceEntry) -> int:
        row = TraceRow.from_domain(entry)
        cur = self._conn.get().execute(
            f"INSERT INTO traces({_COLS}) VALUES ({_PH})", row.model_dump()
        )
        return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def list_by_session(self, session_id: str) -> list[TraceEntry]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM traces WHERE session_id=? ORDER BY created_at ASC, id ASC",
            (session_id,),
        ).fetchall()
        return [TraceRow(**dict(r)).to_domain() for r in rows]

    def list_by_message(self, message_id: str) -> list[TraceEntry]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM traces WHERE message_id=? ORDER BY created_at ASC, id ASC",
            (message_id,),
        ).fetchall()
        return [TraceRow(**dict(r)).to_domain() for r in rows]

    def list_by_task(self, task_id: str) -> list[TraceEntry]:
        """按任务取其全部轨迹，调试单任务用。"""
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM traces WHERE task_id=? ORDER BY created_at ASC, id ASC",
            (task_id,),
        ).fetchall()
        return [TraceRow(**dict(r)).to_domain() for r in rows]

    def aggregate_message_trace(self, message_id: str) -> MessageTrace:
        """从该消息的若干轨迹行重建思考与工具摘要。"""
        return self._aggregate(message_id, self.list_by_message(message_id))

    def batch_aggregate(self, message_ids) -> dict[str, MessageTrace]:
        """一次查询批量聚合多条消息的轨迹，避免逐条查询。无轨迹的消息不在结果中。"""
        ids = list(message_ids)
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM traces "
            f"WHERE message_id IN ({placeholders}) ORDER BY created_at ASC, id ASC",
            ids,
        ).fetchall()
        grouped: dict[str, list[TraceEntry]] = {}
        for row in rows:
            entry = TraceRow(**dict(row)).to_domain()
            if entry.message_id:
                grouped.setdefault(entry.message_id, []).append(entry)
        return {mid: self._aggregate(mid, entries) for mid, entries in grouped.items()}

    def _aggregate(self, message_id: str, entries: list[TraceEntry]) -> MessageTrace:
        """从若干轨迹行重建思考与工具摘要，单条与批量共用。"""
        thinking: list[ThinkingSegment] = []
        tools: dict[str, dict] = {}
        for entry in entries:
            if entry.phase is TracePhase.MODEL_RESPONSE:
                thinking.extend(self._extract_thinking(entry.payload))
            elif entry.phase is TracePhase.TOOL_CALL:
                self._merge_tool_call(tools, entry.payload)
            elif entry.phase is TracePhase.TOOL_RESULT:
                self._merge_tool_result(tools, entry.payload)
        return MessageTrace(
            message_id=message_id,
            thinking=thinking,
            tools=[ToolInvocation(**v) for v in tools.values()],
        )

    def delete_by_session(self, session_id: str) -> None:
        self._conn.get().execute("DELETE FROM traces WHERE session_id=?", (session_id,))

    def delete_by_message(self, message_id: str) -> None:
        self._conn.get().execute("DELETE FROM traces WHERE message_id=?", (message_id,))

    @staticmethod
    def _extract_thinking(payload: dict) -> list[ThinkingSegment]:
        segments = payload.get("thinking_segments") or []
        result: list[ThinkingSegment] = []
        for seg in segments:
            try:
                result.append(ThinkingSegment(**seg))
            except Exception:
                continue
        return result

    @staticmethod
    def _merge_tool_call(tools: dict, payload: dict) -> None:
        tid = payload.get("id")
        if not tid:
            return
        tools[tid] = {
            "tool_call_id": tid,
            "name": payload.get("name", ""),
            "arguments": payload.get("arguments", {}),
            "display": payload.get("display", ""),
            "duration_ms": 0,
            "content": "",
        }

    @staticmethod
    def _merge_tool_result(tools: dict, payload: dict) -> None:
        tid = payload.get("tool_call_id")
        if not tid:
            return
        tool = tools.setdefault(
            tid,
            {
                "tool_call_id": tid,
                "name": payload.get("name", ""),
                "arguments": {},
                "display": "",
                "duration_ms": 0,
                "content": "",
            },
        )
        tool["duration_ms"] = payload.get("duration_ms", 0)
        tool["content"] = payload.get("content", "")
