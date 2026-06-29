"""sessions 表的唯一 SQL 入口。

映射归框架（命名绑定 + model_fields 派生列名），形状转换（title_generated int↔bool）
集中在 SessionRow.to_domain / from_domain。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.session import Session
from chorus.repositories.connection import ConnectionFactory

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
    """sessions 表持久化形状（1:1 贴列）。映射归框架，转换归 to_domain/from_domain。

    title_generated 物理列是 INTEGER，Row 诚实贴 int，to_domain 里 bool()。
    """

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

    def update_meta(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        title_generated: Optional[bool] = None,
        updated_at: Optional[float] = None,
    ) -> None:
        sets: list[str] = []
        params: list[object] = []
        if title is not None:
            sets.append("title=?")
            params.append(title)
        if title_generated is not None:
            sets.append("title_generated=?")
            params.append(1 if title_generated else 0)
        if updated_at is not None:
            sets.append("updated_at=?")
            params.append(updated_at)
        if not sets:
            return
        params.append(session_id)
        self._conn.get().execute(
            f"UPDATE sessions SET {', '.join(sets)} WHERE id=?", params
        )

    def delete(self, session_id: str) -> None:
        """CASCADE 自动带走 messages / traces。"""
        self._conn.get().execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def count(self) -> int:
        row = self._conn.get().execute("SELECT COUNT(*) FROM sessions").fetchone()
        return int(row[0]) if row else 0

    def list_expired(self, ttl_cut: float) -> list[str]:
        rows = self._conn.get().execute(
            "SELECT id FROM sessions WHERE updated_at < ?", (ttl_cut,)
        ).fetchall()
        return [r["id"] for r in rows]
