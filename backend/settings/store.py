"""通用 key-value 配置持久化（SQLite）。

用于存储不需要随会话流转的进程级配置项（例如图像测试模式开关）。
- 独立 DB 文件（默认 backend/data/settings.db），与会话数据生命周期解耦。
- value 以 JSON 编码，支持 bool / int / str / dict / list 等任意可序列化对象。
- 线程安全：每线程一条 sqlite 连接（threading.local）。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
);
"""


class SettingsStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._tls = threading.local()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._tls.conn = conn
        return conn

    def _init_schema(self) -> None:
        self._connect().executescript(_SCHEMA)

    def get(self, key: str, default: Any = None) -> Any:
        row = self._connect().execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return default

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self._connect().execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=strftime('%s','now')",
            (key, payload),
        )

    def delete(self, key: str) -> None:
        self._connect().execute("DELETE FROM settings WHERE key=?", (key,))

    def all(self) -> dict[str, Any]:
        rows = self._connect().execute("SELECT key, value FROM settings").fetchall()
        result: dict[str, Any] = {}
        for k, v in rows:
            try:
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                continue
        return result


_instance: Optional[SettingsStore] = None


def init_settings_store(db_path: Path) -> SettingsStore:
    global _instance
    _instance = SettingsStore(db_path)
    return _instance


def get_settings_store() -> SettingsStore:
    if _instance is None:
        raise RuntimeError("SettingsStore not initialized")
    return _instance
