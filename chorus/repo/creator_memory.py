"""创作者记忆表唯一 SQL 入口，跨会话全局档案。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert

from chorus.domain.memory.models import CreatorMemory
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import CreatorMemoryRecord

_SET_COLS = (
    "kind",
    "description",
    "content",
    "platform",
    "visible_to",
    "created_at",
)


def _to_domain(record: CreatorMemoryRecord) -> CreatorMemory:
    return CreatorMemory(
        **shared_fields(record, CreatorMemory, exclude={"platform", "visible_to"}),
        platform=list(record.platform or []),
        visible_to=list(record.visible_to or []),
    )


def _from_domain(memory: CreatorMemory) -> CreatorMemoryRecord:
    return CreatorMemoryRecord(
        **shared_fields(memory, CreatorMemoryRecord, exclude={"platform", "visible_to"}),
        platform=list(memory.platform),
        visible_to=list(memory.visible_to),
    )


class CreatorMemoryRepository(BaseRepository):
    @read
    def list_all(self, db) -> list[CreatorMemory]:
        rows = db.scalars(select(CreatorMemoryRecord)).all()
        return [_to_domain(row) for row in rows]

    @read
    def get(self, db, memory_id: str) -> Optional[CreatorMemory]:
        record = db.get(CreatorMemoryRecord, memory_id)
        return _to_domain(record) if record else None

    @read
    def get_many(self, db, memory_ids: list[str]) -> list[CreatorMemory]:
        if not memory_ids:
            return []
        rows = db.scalars(
            select(CreatorMemoryRecord).where(CreatorMemoryRecord.id.in_(memory_ids))
        ).all()
        return [_to_domain(row) for row in rows]

    @write
    def upsert(self, db, memory: CreatorMemory) -> None:
        record = _from_domain(memory)
        set_ = {name: getattr(record, name) for name in _SET_COLS}
        db.execute(
            insert(CreatorMemoryRecord)
            .values(id=record.id, **set_)
            .on_conflict_do_update(index_elements=["id"], set_=set_)
        )

    @write
    def delete(self, db, memory_id: str) -> None:
        db.execute(
            delete(CreatorMemoryRecord).where(CreatorMemoryRecord.id == memory_id)
        )

    @write
    def replace_all(self, db, memories: list[CreatorMemory]) -> None:
        db.execute(delete(CreatorMemoryRecord))
        for memory in memories:
            db.add(_from_domain(memory))
