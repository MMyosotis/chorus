"""sessions 表的唯一 SQL 入口。"""

from __future__ import annotations

from typing import Optional

from kitty.domain.models.session import Session
from kitty.repositories.connection import ConnectionFactory

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


class SessionRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def insert(self, session: Session) -> None:
        self._conn.get().execute(
            "INSERT INTO sessions(id, title, title_generated, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session.id,
                session.title,
                1 if session.title_generated else 0,
                session.created_at,
                session.updated_at,
            ),
        )

    def get(self, session_id: str) -> Optional[Session]:
        row = self._conn.get().execute(
            "SELECT id, title, title_generated, created_at, updated_at "
            "FROM sessions WHERE id=?",
            (session_id,),
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_all(self) -> list[Session]:
        rows = self._conn.get().execute(
            "SELECT id, title, title_generated, created_at, updated_at "
            "FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

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
        return [r[0] for r in rows]

    @staticmethod
    def _row_to_session(row) -> Session:
        return Session(
            id=row[0],
            title=row[1],
            title_generated=bool(row[2]),
            created_at=row[3],
            updated_at=row[4],
        )
