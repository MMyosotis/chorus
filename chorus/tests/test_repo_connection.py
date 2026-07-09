"""ConnectionFactory smoke test：线程局部复用、PRAGMA、建表与按列名取行。"""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from chorus.repo.connection import ConnectionFactory


def test_get_reuses_thread_local_conn():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        assert conn.get() is conn.get()  # 同线程复用


def test_get_isolated_per_thread():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        holder = {}

        def worker():
            holder["conn"] = conn.get()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert holder["conn"] is not conn.get()  # 跨线程独立


def test_busy_timeout_pragma():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        row = conn.get().execute("PRAGMA busy_timeout").fetchone()
        assert row[0] == 5000


def test_ensure_schema_and_row_by_name():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        conn.ensure_schema("CREATE TABLE IF NOT EXISTS t(id INTEGER PRIMARY KEY, v TEXT)")
        conn.get().execute("INSERT INTO t(v) VALUES(?)", ("a",))
        rows = conn.get().execute("SELECT v FROM t").fetchall()
        assert [row["v"] for row in rows] == ["a"]


def main():
    test_get_reuses_thread_local_conn()
    test_get_isolated_per_thread()
    test_busy_timeout_pragma()
    test_ensure_schema_and_row_by_name()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
