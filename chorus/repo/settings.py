"""设置表的唯一 SQL 入口，存进程级键值配置，值以 JSON 编码。"""

from __future__ import annotations

import json
import time
from typing import Any

from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


class SettingsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def get(self, key: str, default: Any = None) -> Any:
        row = self._conn.get().execute(
            "SELECT value_json FROM settings WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return default

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self._conn.get().execute(
            "INSERT INTO settings(key, value_json, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (key, payload, time.time()),
        )

    def delete(self, key: str) -> None:
        self._conn.get().execute("DELETE FROM settings WHERE key=?", (key,))
