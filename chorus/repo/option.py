"""选项征询表：每条提问单一行，存提问定义与作答状态。"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.option import OptionPrompt, OptionPromptDef
from chorus.repo.connection import ConnectionFactory
from chorus.repo.mapping import shared_fields

_DDL_TABLE = """
CREATE TABLE IF NOT EXISTS option_prompts (
    prompt_id   TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
)
"""

_DDL_INDEX = "CREATE INDEX IF NOT EXISTS idx_option_prompts_session ON option_prompts(session_id)"


class OptionPromptRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    prompt_id: str
    session_id: str
    prompt: str
    status: str
    created_at: float

    def to_domain(self) -> OptionPrompt:
        definition = json.loads(self.prompt)
        return OptionPrompt(
            **shared_fields(self, OptionPrompt, exclude={"prompt"}),
            **definition,
        )

    @classmethod
    def from_domain(cls, prompt: OptionPrompt) -> "OptionPromptRow":
        definition = prompt.model_dump(
            include=set(OptionPromptDef.model_fields), mode="json",
        )
        return cls(
            **shared_fields(prompt, cls, exclude={"prompt"}),
            prompt=json.dumps(definition, ensure_ascii=False),
        )


_COLS = ", ".join(OptionPromptRow.model_fields)
_PH = ", ".join(f":{field}" for field in OptionPromptRow.model_fields)


class OptionPromptRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = self._conn.get()
        conn.execute(_DDL_TABLE)
        conn.execute(_DDL_INDEX)

    def insert(self, prompt: OptionPrompt) -> None:
        row = OptionPromptRow.from_domain(prompt)
        self._conn.get().execute(
            f"INSERT INTO option_prompts({_COLS}) VALUES ({_PH})",
            row.model_dump(),
        )

    def get(self, prompt_id: str) -> Optional[OptionPrompt]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM option_prompts WHERE prompt_id=?",
            (prompt_id,),
        ).fetchone()
        return OptionPromptRow(**dict(row)).to_domain() if row else None

    def find_open_by_session(self, session_id: str) -> Optional[OptionPrompt]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM option_prompts "
            "WHERE session_id=? AND status='open' ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return OptionPromptRow(**dict(row)).to_domain() if row else None

    def update_answered(self, prompt_id: str) -> None:
        self._conn.get().execute(
            "UPDATE option_prompts SET status='answered' WHERE prompt_id=?",
            (prompt_id,),
        )
