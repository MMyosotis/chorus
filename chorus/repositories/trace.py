"""traces 表的唯一 SQL 入口。

表结构：traces(id, session_id, message_id, iteration, phase, ts, payload_json)，
索引 idx_traces_session_ts / idx_traces_message。trace 与 message 物理解耦，仅靠 message_id 关联。

payload 各 phase 的 schema（写入方约定，聚合方依赖）：
    model_request : {model, messages, tools, max_tokens}
    model_response: {content, finish_reason, tool_calls[], thinking_segments[]}
    tool_call     : {id, name, arguments, display, running_label}
    tool_result   : {tool_call_id, name, content, duration_ms}
"""

from __future__ import annotations

import json
from typing import Optional

from chorus.domain.trace import (
    MessageTrace,
    ThinkingSegment,
    ToolInvocation,
    TraceEntry,
    TracePhase,
)
from chorus.repositories.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_id      TEXT,
    task_id         TEXT,
    source          TEXT NOT NULL DEFAULT 'supervisor',
    iteration       INTEGER,
    phase           TEXT NOT NULL,
    ts              REAL NOT NULL,
    payload_json    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_traces_session_ts ON traces(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_traces_message ON traces(message_id);
CREATE INDEX IF NOT EXISTS idx_traces_task ON traces(task_id, ts);
"""


class TraceRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """旧库平滑加列（开发库重建策略的兜底，避免必须删库）。"""
        cols = {r[1] for r in self._conn.get().execute("PRAGMA table_info(traces)").fetchall()}
        if "task_id" not in cols:
            self._conn.get().execute("ALTER TABLE traces ADD COLUMN task_id TEXT")
        if "source" not in cols:
            self._conn.get().execute(
                "ALTER TABLE traces ADD COLUMN source TEXT NOT NULL DEFAULT 'supervisor'"
            )

    def add(self, entry: TraceEntry) -> int:
        cur = self._conn.get().execute(
            "INSERT INTO traces(session_id, message_id, task_id, source, iteration, phase, ts, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.session_id,
                entry.message_id,
                entry.task_id,
                entry.source,
                entry.iteration,
                entry.phase.value,
                entry.ts,
                json.dumps(entry.payload, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def list_by_session(self, session_id: str) -> list[TraceEntry]:
        rows = self._conn.get().execute(
            "SELECT id, session_id, message_id, task_id, source, iteration, phase, ts, payload_json "
            "FROM traces WHERE session_id=? ORDER BY ts ASC, id ASC",
            (session_id,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_by_message(self, message_id: str) -> list[TraceEntry]:
        rows = self._conn.get().execute(
            "SELECT id, session_id, message_id, task_id, source, iteration, phase, ts, payload_json "
            "FROM traces WHERE message_id=? ORDER BY ts ASC, id ASC",
            (message_id,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_by_task(self, task_id: str) -> list[TraceEntry]:
        """按 task 取该 subagent/scheduler 的全部 trace（调试单 task 用）。"""
        rows = self._conn.get().execute(
            "SELECT id, session_id, message_id, task_id, source, iteration, phase, ts, payload_json "
            "FROM traces WHERE task_id=? ORDER BY ts ASC, id ASC",
            (task_id,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def aggregate_message_trace(self, message_id: str) -> MessageTrace:
        """从该 message 的若干 trace 行重建 thinking + tools。"""
        thinking: list[ThinkingSegment] = []
        tools: dict[str, dict] = {}
        for entry in self.list_by_message(message_id):
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
    def _row_to_entry(row) -> TraceEntry:
        eid, session_id, message_id, task_id, source, iteration, phase, ts, payload_json = row
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            payload = {}
        return TraceEntry(
            id=eid,
            session_id=session_id,
            message_id=message_id,
            task_id=task_id,
            source=source or "supervisor",
            iteration=iteration,
            phase=TracePhase(phase),
            ts=ts,
            payload=payload,
        )

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
            "seq": payload.get("seq", 0),
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
                "seq": 0,
            },
        )
        tool["duration_ms"] = payload.get("duration_ms", 0)
        tool["content"] = payload.get("content", "")
