"""SQLite 连接工厂：线程局部连接，统一启 WAL、外键与超时。"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class ConnectionFactory:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._tls = threading.local()

    def get(self) -> sqlite3.Connection:
        """返回当前线程的连接，首次调用时建立。"""
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.row_factory = sqlite3.Row  # 行按列名访问
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._tls.conn = conn
        return conn

    def ensure_schema(self, ddl: str) -> None:
        """执行一段建表 DDL（幂等 CREATE TABLE IF NOT EXISTS）。"""
        self.get().executescript(ddl)
