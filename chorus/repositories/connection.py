"""SQLite 连接工厂：线程局部连接，统一 PRAGMA 配置。

每个线程一条连接（threading.local），WAL + NORMAL 同步 + 外键约束 + busy_timeout。
transaction() 上下文管理器供 service/agents 开事务（repo 永不开）。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
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
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._tls.conn = conn
        return conn

    def ensure_schema(self, ddl: str) -> None:
        """执行一段建表 DDL（幂等 CREATE TABLE IF NOT EXISTS）。"""
        self.get().executescript(ddl)

    @contextmanager
    def transaction(self):
        """显式事务：BEGIN; yield; COMMIT; except ROLLBACK。不可嵌套（sqlite 不支持裸 BEGIN 嵌套）。"""
        conn = self.get()
        if getattr(self._tls, "in_txn", False):
            raise RuntimeError("transaction 不可嵌套")
        conn.execute("BEGIN")
        self._tls.in_txn = True
        try:
            yield
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            self._tls.in_txn = False
