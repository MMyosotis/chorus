"""Row 与表列集一致性契约：每个 Row 字段集等于实际表列名集。

防漂移：DDL 加列但 Row 漏字段（或反之）即失败。settings 是纯 KV 无 Row，不在此列。
"""
from __future__ import annotations

from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRow, MessageRepository
from chorus.repo.session import SessionRow, SessionRepository
from chorus.repo.task import TaskRow, TaskRepository
from chorus.repo.task_progress import TaskProgressRepository, TaskProgressRow
from chorus.repo.task_artifacts import TaskArtifactsRow, TaskArtifactsRepository
from chorus.repo.trace import TraceRow, TraceRepository
from chorus.tests._helpers import fresh_conn


def _columns(conn: ConnectionFactory, table: str) -> set[str]:
    rows = conn.get().execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def test_row_fields_match_table_columns():
    conn = fresh_conn()
    # 各 repo 构造时建表
    SessionRepository(conn)
    MessageRepository(conn)
    TraceRepository(conn)
    TaskRepository(conn)
    TaskArtifactsRepository(conn)
    TaskProgressRepository(conn)

    cases = [
        ("messages", MessageRow),
        ("traces", TraceRow),
        ("tasks", TaskRow),
        ("task_artifacts", TaskArtifactsRow),
        ("task_progress", TaskProgressRow),
        ("sessions", SessionRow),
    ]
    for table, row_cls in cases:
        actual = _columns(conn, table)
        declared = set(row_cls.model_fields)
        assert actual == declared, (
            f"{table}: DDL 列 {actual ^ declared} 与 {row_cls.__name__}.model_fields 不一致"
            f"（DDL 独有={actual - declared}, Row 独有={declared - actual}）"
        )


def main():
    test_row_fields_match_table_columns()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
