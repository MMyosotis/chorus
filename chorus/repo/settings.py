"""设置表的唯一 SQL 入口，存进程级键值配置，纯字符串值。值的序列化语义由调用方承担。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert

from chorus.repo.base import BaseRepository, read, write
from chorus.repo.models import SettingsRecord


class SettingsRepository(BaseRepository):
    @read
    def get(self, db, key: str, default: Optional[str] = None) -> Optional[str]:
        r = db.get(SettingsRecord, key)
        return r.value if r is not None else default

    @write
    def set(self, db, key: str, value: str) -> None:
        db.execute(
            insert(SettingsRecord)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )

    @write
    def delete(self, db, key: str) -> None:
        db.execute(delete(SettingsRecord).where(SettingsRecord.key == key))
