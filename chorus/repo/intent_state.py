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
    missing_slots         TEXT NOT NULL,
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
    missing_slots: str
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
            missing_slots=json.loads(self.missing_slots),
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
            missing_slots=json.dumps(state.missing_slots, ensure_ascii=False),
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
        self._conn.ensure_schema(_DDL)

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
