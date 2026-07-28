"""build_engine smoke：建连 PRAGMA、幂等建表与跨线程取连接。"""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from sqlalchemy import text

from chorus.repo.engine import build_engine


def test_pragma_on_connect():
    with tempfile.TemporaryDirectory() as tmp:
        engine = build_engine(Path(tmp) / "t.db")
        with engine.connect() as db:
            assert db.execute(text("PRAGMA busy_timeout")).scalar() == 5000
            assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert db.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_create_all_creates_tables():
    with tempfile.TemporaryDirectory() as tmp:
        engine = build_engine(Path(tmp) / "t.db")
        with engine.connect() as db:
            names = {row[0] for row in db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert {"sessions", "messages", "tasks"} <= names


def test_connect_cross_thread():
    """check_same_thread=False 允许跨线程从同一 Engine 取连接。"""
    with tempfile.TemporaryDirectory() as tmp:
        engine = build_engine(Path(tmp) / "t.db")
        holder = {}

        def worker():
            with engine.connect() as db:
                holder["ok"] = db.execute(text("SELECT 1")).scalar()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert holder["ok"] == 1


def main():
    test_pragma_on_connect()
    test_create_all_creates_tables()
    test_connect_cross_thread()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
