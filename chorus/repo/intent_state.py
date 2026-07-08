"""意图状态表：每个会话保留一份最新结构化快照。"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.intent import IntentState
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS intent_states (
    session_id            TEXT PRIMARY KEY,
    intent_status         TEXT NOT NULL,
    goal                  TEXT NOT NULL DEFAULT '',
    known_slots           TEXT NOT NULL DEFAULT '{}',
    missing_slots         TEXT NOT NULL DEFAULT '[]',
    confirmation_summary  TEXT,
    version               INTEGER NOT NULL DEFAULT 0,
    updated_at            REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""


class IntentStateRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    session_id: str
    intent_status: str
    goal: str = ""
    known_slots: str = "{}"
    missing_slots: str = "[]"
    confirmation_summary: Optional[str] = None
    version: int = 0
    updated_at: float

    def to_domain(self) -> IntentState:
        return IntentState(
            session_id=self.session_id,
            intent_status=self.intent_status,
            goal=self.goal,
            known_slots=_loads(self.known_slots, {}),
            missing_slots=_loads(self.missing_slots, []),
            confirmation_summary=_loads(self.confirmation_summary, None),
            version=self.version,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, state: IntentState) -> "IntentStateRow":
        summary = None
        if state.confirmation_summary is not None:
            summary = json.dumps(
                state.confirmation_summary.model_dump(mode="json"),
                ensure_ascii=False,
            )
        return cls(
            session_id=state.session_id,
            intent_status=state.intent_status,
            goal=state.goal,
            known_slots=json.dumps(state.known_slots, ensure_ascii=False),
            missing_slots=json.dumps(state.missing_slots, ensure_ascii=False),
            confirmation_summary=summary,
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


def _loads(raw: Optional[str], default):
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default
