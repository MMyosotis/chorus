"""消息表的唯一 SQL 入口，按消息粒度逐行存储。

助手消息的展示元数据存轨迹表，靠消息标识关联聚合。映射归框架，形状转换集中在行模型。
"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.message import (
    AssistantMessage,
    Message,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT,
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    tool_name       TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id);
"""


class MessageRow(BaseModel):
    """消息表持久化形状，与列一一对应。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    session_id: str
    role: str
    content: Optional[str] = None
    tool_calls_json: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    created_at: float

    def to_domain(self) -> Message:
        if self.role == "user":
            return UserMessage(id=self.id, session_id=self.session_id,
                               created_at=self.created_at, content=self.content or "")
        if self.role == "assistant":
            return AssistantMessage(id=self.id, session_id=self.session_id,
                                    created_at=self.created_at, content=self.content,
                                    tool_calls=self._parse_tool_calls(self.tool_calls_json))
        if self.role == "tool":
            return ToolMessage(id=self.id, session_id=self.session_id,
                               created_at=self.created_at,
                               tool_call_id=self.tool_call_id or "",
                               name=self.tool_name or "",
                               content=self.content or "")
        raise ValueError(f"unknown role: {self.role}")

    @classmethod
    def from_domain(cls, msg: Message) -> "MessageRow":
        if isinstance(msg, UserMessage):
            return cls(id=msg.id, session_id=msg.session_id,
                       role="user", content=msg.content, created_at=msg.created_at)
        if isinstance(msg, AssistantMessage):
            return cls(id=msg.id, session_id=msg.session_id,
                       role="assistant", content=msg.content,
                       tool_calls_json=cls._dump_tool_calls(msg.tool_calls),
                       created_at=msg.created_at)
        if isinstance(msg, ToolMessage):
            return cls(id=msg.id, session_id=msg.session_id,
                       role="tool", content=msg.content,
                       tool_call_id=msg.tool_call_id, tool_name=msg.name,
                       created_at=msg.created_at)
        raise TypeError(f"unsupported message type: {type(msg)}")

    @staticmethod
    def _parse_tool_calls(raw: Optional[str]) -> list[ToolCallSpec]:
        """解析工具调用 JSON，脏数据退化为空。"""
        if not raw:
            return []
        try:
            return [ToolCallSpec(**tc) for tc in json.loads(raw)]
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def _dump_tool_calls(tool_calls: Optional[list[ToolCallSpec]]) -> Optional[str]:
        if not tool_calls:
            return None
        return json.dumps([call.model_dump() for call in tool_calls], ensure_ascii=False)


_COLS = ", ".join(MessageRow.model_fields)
_PH = ", ".join(f":{field}" for field in MessageRow.model_fields)


class MessageRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(self, message: Message) -> None:
        """单条消息入库。"""
        row = MessageRow.from_domain(message)
        self._conn.get().execute(
            f"INSERT INTO messages({_COLS}) VALUES ({_PH})", row.model_dump()
        )

    def list_by_session(self, session_id: str) -> list[Message]:
        """按标识升序返回该会话全部消息，即写入顺序。"""
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [MessageRow(**dict(row)).to_domain() for row in rows]

    def get(self, message_id: str) -> Optional[Message]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        return MessageRow(**dict(row)).to_domain() if row else None
