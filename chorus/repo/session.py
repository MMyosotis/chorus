"""会话表的唯一 SQL 入口。布尔与整型的转换集中在转换函数。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select, update

from chorus.domain.session import Session
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import SessionRecord


def _to_domain(r: SessionRecord) -> Session:
    return Session(
        **shared_fields(r, Session, exclude={"title_generated"}),
        title_generated=bool(r.title_generated),
    )


def _from_domain(s: Session) -> SessionRecord:
    return SessionRecord(
        **shared_fields(s, SessionRecord, exclude={"title_generated"}),
        title_generated=1 if s.title_generated else 0,
    )


class SessionRepository(BaseRepository):
    @write
    def insert(self, db, session: Session) -> None:
        db.add(_from_domain(session))

    @read
    def get(self, db, session_id: str) -> Optional[Session]:
        r = db.get(SessionRecord, session_id)
        return _to_domain(r) if r else None

    @read
    def list_all(self, db) -> list[Session]:
        rs = db.scalars(
            select(SessionRecord).order_by(SessionRecord.updated_at.desc())
        ).all()
        return [_to_domain(r) for r in rs]

    @write
    def touch(self, db, session_id: str, updated_at: float) -> None:
        db.execute(
            update(SessionRecord).where(SessionRecord.id == session_id)
            .values(updated_at=updated_at)
        )

    @write
    def set_title(
        self, db, session_id: str, *, title: str, title_generated: bool, updated_at: float
    ) -> None:
        db.execute(
            update(SessionRecord).where(SessionRecord.id == session_id).values(
                title=title,
                title_generated=1 if title_generated else 0,
                updated_at=updated_at,
            )
        )

    @write
    def delete(self, db, session_id: str) -> None:
        """级联删除关联消息与轨迹靠外键 ON DELETE CASCADE。"""
        db.execute(delete(SessionRecord).where(SessionRecord.id == session_id))

    @read
    def count(self, db) -> int:
        return int(db.scalar(select(func.count(SessionRecord.id))) or 0)

    @read
    def list_expired(self, db, ttl_cut: float) -> list[str]:
        return list(
            db.scalars(
                select(SessionRecord.id).where(SessionRecord.updated_at < ttl_cut)
            ).all()
        )
