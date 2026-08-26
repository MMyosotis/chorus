"""模型现场表的唯一 SQL 入口：存发给模型的消息行，压缩在此表落笔。"""
from __future__ import annotations

from sqlalchemy import delete, select, update

from chorus.domain.message import Message
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.message import from_domain, to_domain
from chorus.repo.models import ProviderMessageRecord


class ProviderMessageRepository(BaseRepository):
    @write
    def append(self, db, message: Message) -> None:
        """单条现场行入库。"""
        db.add(from_domain(message, ProviderMessageRecord))

    @read
    def list_by_session(self, db, session_id: str) -> list[Message]:
        """按标识升序返回该会话全部现场行，即模型所见。"""
        rs = db.scalars(
            select(ProviderMessageRecord).where(ProviderMessageRecord.session_id == session_id)
            .order_by(ProviderMessageRecord.id)
        ).all()
        return [to_domain(r) for r in rs]

    @write
    def elide(self, db, session_id: str, message_ids: list[str], content: str) -> None:
        """批量把现场行正文换为占位。"""
        db.execute(
            update(ProviderMessageRecord).where(
                ProviderMessageRecord.session_id == session_id,
                ProviderMessageRecord.id.in_(message_ids),
            ).values(content=content)
        )

    @write
    def update_content(self, db, message_id: str, content: str) -> None:
        """按标识改写正文，行不存在则空改。"""
        db.execute(
            update(ProviderMessageRecord).where(ProviderMessageRecord.id == message_id)
            .values(content=content)
        )

    @write
    def replace_with_summary(self, db, session_id: str, message: Message) -> None:
        """整段覆写：清空该会话现场，只留一条摘要行。"""
        db.execute(
            delete(ProviderMessageRecord).where(ProviderMessageRecord.session_id == session_id)
        )
        db.add(from_domain(message, ProviderMessageRecord))
