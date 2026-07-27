"""意图状态表：每个会话保留一份最新结构化快照。"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.intent import IntentState, IntentStatus
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS intent_states (
    session_id            TEXT PRIMARY KEY,
    intent_status         TEXT NOT NULL,
    topic                 TEXT NOT NULL,
    platform              TEXT NOT NULL,
    format                TEXT NOT NULL,
    style                 TEXT NOT NULL,
    image_count           INTEGER NOT NULL,
    extra                 TEXT NOT NULL,
    progress_percent      INTEGER NOT NULL CHECK(progress_percent BETWEEN 0 AND 100),
    version               INTEGER NOT NULL,
    updated_at            REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""


class IntentStateRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    session_id: str
    intent_status: IntentStatus
    topic: str
    platform: str
    format: str
    style: str
    image_count: int
    extra: str
    progress_percent: int
    version: int
    updated_at: float

    def to_domain(self) -> IntentState:
        return IntentState(
            session_id=self.session_id,
            intent_status=self.intent_status,
            topic=self.topic,
            platform=self.platform,
            format=self.format,
            style=self.style,
            image_count=self.image_count,
            extra=json.loads(self.extra),
            progress_percent=self.progress_percent,
            version=self.version,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, state: IntentState) -> "IntentStateRow":
        return cls(
            session_id=state.session_id,
            intent_status=state.intent_status,
            topic=state.topic,
            platform=state.platform,
            format=state.format,
            style=state.style,
            image_count=state.image_count,
            extra=json.dumps(state.extra, ensure_ascii=False),
            progress_percent=state.progress_percent,
            version=state.version,
            updated_at=state.updated_at,
        )


_COLS = ", ".join(IntentStateRow.model_fields)
_PH = ", ".join(f":{field}" for field in IntentStateRow.model_fields)
_UPDATES = ", ".join(
    f"{field}=excluded.{field}" for field in IntentStateRow.model_fields if field != "session_id"
)


class IntentStateRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """建新表，并把旧 missing_slots 契约一次性迁移为进度百分比。"""
        conn = self._conn.get()
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(intent_states)").fetchall()
        }
        if not columns:
            conn.execute(_DDL)
            return
        if "progress_percent" in columns and "missing_slots" not in columns:
            return
        if "missing_slots" not in columns:
            raise RuntimeError(f"unsupported intent_states schema: {sorted(columns)}")

        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("ALTER TABLE intent_states RENAME TO intent_states_legacy")
            conn.execute(_DDL)
            conn.execute(
                """
                INSERT INTO intent_states(
                    session_id, intent_status, topic, platform, format, style,
                    image_count, extra, progress_percent, version, updated_at
                )
                SELECT
                    session_id, intent_status, topic, platform, format, style,
                    image_count, extra,
                    CASE intent_status
                        WHEN 'empty' THEN 0
                        WHEN 'capturing' THEN 35
                        WHEN 'needs_clarification' THEN 65
                        ELSE 100
                    END,
                    version, updated_at
                FROM intent_states_legacy
                """
            )
            conn.execute("DROP TABLE intent_states_legacy")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def get(self, session_id: str) -> Optional[IntentState]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM intent_states WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return IntentStateRow(**dict(row)).to_domain() if row else None

    def upsert(self, state: IntentState) -> None:
        row = IntentStateRow.from_domain(state)
        self._conn.get().execute(
            f"INSERT INTO intent_states({_COLS}) VALUES ({_PH}) "
            f"ON CONFLICT(session_id) DO UPDATE SET {_UPDATES}",
            row.model_dump(),
        )

    def delete(self, session_id: str) -> None:
        self._conn.get().execute("DELETE FROM intent_states WHERE session_id=?", (session_id,))
