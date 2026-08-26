"""进度快照表唯一 SQL 入口：一任务一行，upsert 覆盖。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from chorus.domain.task.progress import TaskProgress
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import TaskProgressRecord


def _to_domain(r: TaskProgressRecord) -> TaskProgress:
    return TaskProgress(**shared_fields(r, TaskProgress))


def _upsert(db, task_id: str, **values) -> None:
    db.execute(
        insert(TaskProgressRecord)
        .values(task_id=task_id, **values)
        .on_conflict_do_update(index_elements=["task_id"], set_=values)
    )


class TaskProgressRepository(BaseRepository):
    @write
    def set_composing(self, db, task_id: str, chars: int, units: int) -> None:
        _upsert(db, task_id, composing_chars=chars, composing_units=units)

    @write
    def set_composing_chars(self, db, task_id: str, chars: int) -> None:
        _upsert(db, task_id, composing_chars=chars)

    @write
    def set_composing_units(self, db, task_id: str, units: int) -> None:
        _upsert(db, task_id, composing_units=units)

    @write
    def set_composing_label(self, db, task_id: str, label: str) -> None:
        _upsert(db, task_id, composing_label=label)

    @write
    def set_aside(self, db, task_id: str, aside: str) -> None:
        _upsert(db, task_id, aside=aside)

    @write
    def set_signal(self, db, task_id: str, signal: str) -> None:
        _upsert(db, task_id, last_signal=signal)

    @write
    def set_activity(self, db, task_id: str, kind: str, detail: str = "") -> None:
        _upsert(db, task_id, activity_kind=kind, activity_detail=detail)

    @read
    def load(self, db, task_id: str) -> Optional[TaskProgress]:
        r = db.get(TaskProgressRecord, task_id)
        return _to_domain(r) if r else None

    @read
    def load_many(self, db, task_ids: list[str]) -> dict[str, TaskProgress]:
        if not task_ids:
            return {}
        rs = db.scalars(
            select(TaskProgressRecord).where(TaskProgressRecord.task_id.in_(task_ids))
        ).all()
        return {r.task_id: _to_domain(r) for r in rs}
