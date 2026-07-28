"""任务内容表的唯一 SQL 入口，与任务表一一对应。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from chorus.domain.task import TaskContent
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import TaskContentRecord


def _to_domain(r: TaskContentRecord) -> TaskContent:
    return TaskContent(**shared_fields(r, TaskContent))


def _from_domain(c: TaskContent) -> TaskContentRecord:
    return TaskContentRecord(**shared_fields(c, TaskContentRecord))


class TaskContentRepository(BaseRepository):
    @write
    def insert(self, db, content: TaskContent) -> None:
        db.add(_from_domain(content))

    @read
    def load(self, db, task_id: str) -> Optional[TaskContent]:
        r = db.get(TaskContentRecord, task_id)
        return _to_domain(r) if r else None

    @read
    def load_many(self, db, task_ids: list[str]) -> dict[str, TaskContent]:
        if not task_ids:
            return {}
        rs = db.scalars(
            select(TaskContentRecord).where(TaskContentRecord.task_id.in_(task_ids))
        ).all()
        return {r.task_id: _to_domain(r) for r in rs}

    @write
    def set_error(self, db, task_id: str, error: str) -> None:
        db.execute(
            insert(TaskContentRecord)
            .values(task_id=task_id, invoke_message="", error=error)
            .on_conflict_do_update(index_elements=["task_id"], set_={"error": error})
        )

    @write
    def set_feedback(self, db, task_id: str, feedback: str) -> None:
        db.execute(
            insert(TaskContentRecord)
            .values(task_id=task_id, invoke_message="", feedback=feedback)
            .on_conflict_do_update(
                index_elements=["task_id"], set_={"feedback": feedback}
            )
        )
