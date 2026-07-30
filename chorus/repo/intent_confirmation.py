"""意图确认留档表：每次待确认挂起单一行，存意图快照与作答状态。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from chorus.domain.intent import IntentConfirmation, IntentConfirmationAnswer, IntentSnapshot
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import IntentConfirmationRecord


def _to_domain(r: IntentConfirmationRecord) -> IntentConfirmation:
    return IntentConfirmation(
        **shared_fields(r, IntentConfirmation),
        **r.snapshot,
    )


def _from_domain(c: IntentConfirmation) -> IntentConfirmationRecord:
    snapshot = c.model_dump(include=set(IntentSnapshot.model_fields), mode="json")
    if c.answer:
        snapshot["answer"] = c.answer.model_dump(mode="json", exclude_none=True)
    return IntentConfirmationRecord(
        **shared_fields(c, IntentConfirmationRecord),
        snapshot=snapshot,
    )


class IntentConfirmationRepository(BaseRepository):
    @write
    def insert(self, db, confirmation: IntentConfirmation) -> None:
        db.add(_from_domain(confirmation))

    @read
    def find_open_by_session(self, db, session_id: str) -> Optional[IntentConfirmation]:
        r = db.scalars(
            select(IntentConfirmationRecord)
            .where(
                IntentConfirmationRecord.session_id == session_id,
                IntentConfirmationRecord.status == "open",
            )
            .order_by(IntentConfirmationRecord.created_at.desc())
            .limit(1)
        ).first()
        return _to_domain(r) if r else None

    @read
    def find_by_session(self, db, session_id: str) -> list[IntentConfirmation]:
        rows = db.scalars(
            select(IntentConfirmationRecord)
            .where(IntentConfirmationRecord.session_id == session_id)
            .order_by(IntentConfirmationRecord.created_at.asc())
        ).all()
        return [_to_domain(row) for row in rows]

    @write
    def update_answered(self, db, session_id: str, answer: IntentConfirmationAnswer) -> None:
        record = db.scalars(
            select(IntentConfirmationRecord)
            .where(
                IntentConfirmationRecord.session_id == session_id,
                IntentConfirmationRecord.status == "open",
            )
            .order_by(IntentConfirmationRecord.created_at.desc())
            .limit(1)
        ).first()
        if record is None:
            return
        snapshot = dict(record.snapshot)
        snapshot["answer"] = answer.model_dump(mode="json", exclude_none=True)
        record.snapshot = snapshot
        record.status = "answered"
