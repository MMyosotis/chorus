"""设置表的唯一 SQL 入口，存进程级键值配置，纯字符串值。值的序列化语义由调用方承担。"""

from __future__ import annotations

from typing import Optional

from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SettingsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self._conn.get().execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default

    def set(self, key: str, value: str) -> None:
        self._conn.get().execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def delete(self, key: str) -> None:
        self._conn.get().execute("DELETE FROM settings WHERE key=?", (key,))
