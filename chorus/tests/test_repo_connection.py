"""ConnectionFactory smoke test：transaction 提交/回滚/不可嵌套 + busy_timeout PRAGMA。

运行：``.venv/bin/python -m kitty.tests.test_repo_connection``
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chorus.repositories.connection import ConnectionFactory


def test_transaction_commit():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        conn.ensure_schema("CREATE TABLE IF NOT EXISTS t(id INTEGER PRIMARY KEY, v TEXT)")
        with conn.transaction():
            conn.get().execute("INSERT INTO t(v) VALUES(?)", ("a",))
        rows = conn.get().execute("SELECT v FROM t").fetchall()
        assert [r["v"] for r in rows] == ["a"]  # row_factory=Row，按列名取


def test_transaction_rollback():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        conn.ensure_schema("CREATE TABLE IF NOT EXISTS t(id INTEGER PRIMARY KEY, v TEXT)")
        with pytest.raises(ValueError):
            with conn.transaction():
                conn.get().execute("INSERT INTO t(v) VALUES(?)", ("a",))
                raise ValueError("boom")
        rows = conn.get().execute("SELECT v FROM t").fetchall()
        assert rows == []  # 回滚


def test_transaction_no_nesting():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        with conn.transaction():
            with pytest.raises(RuntimeError):
                with conn.transaction():
                    pass


def test_busy_timeout_pragma():
    with tempfile.TemporaryDirectory() as tmp:
        conn = ConnectionFactory(Path(tmp) / "t.db")
        row = conn.get().execute("PRAGMA busy_timeout").fetchone()
        assert row[0] == 5000


def main():
    test_transaction_commit()
    test_transaction_rollback()
    test_transaction_no_nesting()
    test_busy_timeout_pragma()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
