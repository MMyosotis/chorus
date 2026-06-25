"""settings 表的唯一 SQL 入口（与 sessions/messages/traces/tasks 同库）。

存储进程级 KV 配置（如 image_test_mode）。value 以 JSON 编码。
"""

from __future__ import annotations

import json
import time
from typing import Any

from kitty.repositories.connection import ConnectionFactory

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
            return json.loads(row[0])
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

    def all(self) -> dict[str, Any]:
        rows = self._conn.get().execute("SELECT key, value_json FROM settings").fetchall()
        result: dict[str, Any] = {}
        for k, v in rows:
            try:
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                continue
        return result
