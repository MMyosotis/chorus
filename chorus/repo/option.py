"""选项征询表：每条提问单一行，存提问定义与作答状态。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from chorus.domain.option import OptionAnswer, OptionPrompt, OptionPromptDef
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import OptionPromptRecord


def _to_domain(r: OptionPromptRecord) -> OptionPrompt:
    return OptionPrompt(
        **shared_fields(r, OptionPrompt),
        **r.prompt,
    )


def _from_domain(p: OptionPrompt) -> OptionPromptRecord:
    definition = p.model_dump(include=set(OptionPromptDef.model_fields), mode="json")
    return OptionPromptRecord(
        **shared_fields(p, OptionPromptRecord),
        prompt=definition,
    )


class OptionPromptRepository(BaseRepository):
    @write
    def insert(self, db, prompt: OptionPrompt) -> None:
        db.add(_from_domain(prompt))

    @read
    def get(self, db, prompt_id: str) -> Optional[OptionPrompt]:
        r = db.get(OptionPromptRecord, prompt_id)
        return _to_domain(r) if r else None

    @read
    def find_open_by_session(self, db, session_id: str) -> Optional[OptionPrompt]:
        r = db.scalars(
            select(OptionPromptRecord)
            .where(
                OptionPromptRecord.session_id == session_id,
                OptionPromptRecord.status == "open",
            )
            .order_by(OptionPromptRecord.created_at.desc())
            .limit(1)
        ).first()
        return _to_domain(r) if r else None

    @read
    def find_by_session(self, db, session_id: str) -> list[OptionPrompt]:
        rows = db.scalars(
            select(OptionPromptRecord)
            .where(OptionPromptRecord.session_id == session_id)
            .order_by(OptionPromptRecord.created_at.asc())
        ).all()
        return [_to_domain(row) for row in rows]

    @write
    def update_answered(self, db, session_id: str, answers: list[OptionAnswer]) -> None:
        record = db.scalars(
            select(OptionPromptRecord)
            .where(
                OptionPromptRecord.session_id == session_id,
                OptionPromptRecord.status == "open",
            )
            .order_by(OptionPromptRecord.created_at.desc())
            .limit(1)
        ).first()
        if record is None:
            return
        prompt: dict[str, Any] = dict(record.prompt)
        prompt["answers"] = [
            answer.model_dump(mode="json", exclude_none=True) for answer in answers
        ]
        record.prompt = prompt
        record.status = "answered"
