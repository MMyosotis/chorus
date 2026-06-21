"""messages 表的唯一 SQL 入口。

按消息粒度逐行存储（user / assistant / tool）。assistant 的 thinking/tools 展示
元数据存在 traces 表，靠 message_id 关联，由 TraceRepository 聚合。
"""

from __future__ import annotations

import json
from typing import Optional

from kitty.domain.message import (
    AssistantMessage,
    Message,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from kitty.repositories.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT,
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    tool_name       TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_msg_session_seq ON messages(session_id, seq);
"""


class MessageRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(self, message: Message) -> None:
        """单条消息入库。"""
        self._conn.get().execute(
            "INSERT INTO messages("
            "id, session_id, seq, role, content, tool_calls_json, "
            "tool_call_id, tool_name, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._message_to_row(message),
        )

    def list_by_session(self, session_id: str) -> list[Message]:
        """按 seq 升序返回该会话全部消息。"""
        rows = self._conn.get().execute(
            "SELECT id, session_id, seq, role, content, tool_calls_json, "
            "tool_call_id, tool_name, created_at "
            "FROM messages WHERE session_id=? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def get(self, message_id: str) -> Optional[Message]:
        row = self._conn.get().execute(
            "SELECT id, session_id, seq, role, content, tool_calls_json, "
            "tool_call_id, tool_name, created_at FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        return self._row_to_message(row) if row else None

    def next_seq(self, session_id: str) -> int:
        row = self._conn.get().execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    # 行 ↔ 模型映射
    @staticmethod
    def _message_to_row(message: Message) -> tuple:
        mid, cid, seq, created = message.id, message.session_id, message.seq, message.created_at
        if isinstance(message, UserMessage):
            return (mid, cid, seq, "user", message.content, None, None, None, created)
        if isinstance(message, AssistantMessage):
            tool_calls_json = (
                json.dumps([tc.model_dump() for tc in message.tool_calls], ensure_ascii=False)
                if message.tool_calls
                else None
            )
            return (mid, cid, seq, "assistant", message.content, tool_calls_json, None, None, created)
        if isinstance(message, ToolMessage):
            return (mid, cid, seq, "tool", message.content, None, message.tool_call_id, message.name, created)
        raise TypeError(f"unsupported message type: {type(message)}")

    @staticmethod
    def _row_to_message(row) -> Message:
        mid, cid, seq, role, content, tool_calls_json, tool_call_id, tool_name, created = row
        if role == "user":
            return UserMessage(id=mid, session_id=cid, seq=seq, created_at=created, content=content or "")
        if role == "assistant":
            tool_calls: list[ToolCallSpec] = []
            if tool_calls_json:
                try:
                    tool_calls = [ToolCallSpec(**tc) for tc in json.loads(tool_calls_json)]
                except (json.JSONDecodeError, TypeError):
                    tool_calls = []
            return AssistantMessage(
                id=mid, session_id=cid, seq=seq, created_at=created,
                content=content, tool_calls=tool_calls,
            )
        if role == "tool":
            return ToolMessage(
                id=mid, session_id=cid, seq=seq, created_at=created,
                tool_call_id=tool_call_id or "", name=tool_name or "", content=content or "",
            )
        raise ValueError(f"unknown role: {role}")
