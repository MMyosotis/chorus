"""意图状态表：每个会话保留一份最新结构化快照。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert

from chorus.domain.intent import IntentState
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import IntentStateRecord

_SET_COLS = (
    "intent_status", "topic", "platform", "format", "style", "image_count",
    "extra", "progress_percent", "version", "updated_at",
)


def _to_domain(r: IntentStateRecord) -> IntentState:
    return IntentState(
        **shared_fields(r, IntentState, exclude={"extra"}),
        extra=dict(r.extra or {}),
    )


def _from_domain(s: IntentState) -> IntentStateRecord:
    return IntentStateRecord(
        **shared_fields(s, IntentStateRecord, exclude={"extra"}),
        extra=dict(s.extra),
    )


class IntentStateRepository(BaseRepository):
    @read
    def get(self, db, session_id: str) -> Optional[IntentState]:
        r = db.get(IntentStateRecord, session_id)
        return _to_domain(r) if r else None

    @write
    def upsert(self, db, state: IntentState) -> None:
        r = _from_domain(state)
        set_ = {name: getattr(r, name) for name in _SET_COLS}
        db.execute(
            insert(IntentStateRecord)
            .values(session_id=r.session_id, **set_)
            .on_conflict_do_update(index_elements=["session_id"], set_=set_)
        )

    @write
    def delete(self, db, session_id: str) -> None:
        db.execute(
            delete(IntentStateRecord)
            .where(IntentStateRecord.session_id == session_id)
        )
