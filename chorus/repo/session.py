"""会话表的唯一 SQL 入口。映射归框架，布尔与整型的转换集中在行模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.session import Session
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    title_generated INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_updated ON sessions(updated_at DESC);
"""


class SessionRow(BaseModel):
    """会话表持久化形状，与列一一对应。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    title: str
    title_generated: int
    created_at: float
    updated_at: float

    def to_domain(self) -> Session:
        return Session(
            id=self.id,
            title=self.title,
            title_generated=bool(self.title_generated),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, session: Session) -> "SessionRow":
        return cls(
            id=session.id,
            title=session.title,
            title_generated=1 if session.title_generated else 0,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


_COLS = ", ".join(SessionRow.model_fields)
_PH = ", ".join(f":{k}" for k in SessionRow.model_fields)


class SessionRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def insert(self, session: Session) -> None:
        row = SessionRow.from_domain(session)
        self._conn.get().execute(
            f"INSERT INTO sessions({_COLS}) VALUES ({_PH})", row.model_dump()
        )

    def get(self, session_id: str) -> Optional[Session]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM sessions WHERE id=?",
            (session_id,),
        ).fetchone()
        return SessionRow(**dict(row)).to_domain() if row else None

    def list_all(self) -> list[Session]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [SessionRow(**dict(r)).to_domain() for r in rows]

    def touch(self, session_id: str, updated_at: float) -> None:
        """刷新会话更新时间。"""
        self._conn.get().execute(
            "UPDATE sessions SET updated_at=? WHERE id=?", (updated_at, session_id)
        )

    def set_title(
        self, session_id: str, *, title: str, title_generated: bool, updated_at: float
    ) -> None:
        self._conn.get().execute(
            "UPDATE sessions SET title=?, title_generated=?, updated_at=? WHERE id=?",
            (title, 1 if title_generated else 0, updated_at, session_id),
        )

    def delete(self, session_id: str) -> None:
        """级联删除关联消息与轨迹。"""
        self._conn.get().execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def count(self) -> int:
        row = self._conn.get().execute("SELECT COUNT(*) FROM sessions").fetchone()
        return int(row[0]) if row else 0

    def list_expired(self, ttl_cut: float) -> list[str]:
        rows = self._conn.get().execute(
            "SELECT id FROM sessions WHERE updated_at < ?", (ttl_cut,)
        ).fetchall()
        return [r["id"] for r in rows]
