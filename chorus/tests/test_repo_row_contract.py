"""Row ↔ DDL 列集一致性契约：每个 XxxRow.model_fields 键集必须等于实际表列名集。

防漂移红线：DDL 加列但 Row 漏字段（或反之）。注意 extra="forbid" + strict=True 已在
运行时每次读写强校验（多列/类型不符即报错），本测试把这条不变量显式文档化——若有人为
绕过报错而放松 forbid/strict，此处失败提醒。settings 是纯 KV 无 Row，不在此列。

运行：``.venv/bin/python -m chorus.tests.test_repo_row_contract``
"""
from __future__ import annotations

from chorus.repositories.connection import ConnectionFactory
from chorus.repositories.message import MessageRow, MessageRepository
from chorus.repositories.session import SessionRow, SessionRepository
from chorus.repositories.task import TaskRow, TaskRepository
from chorus.repositories.task_artifacts import TaskArtifactsRow, TaskArtifactsRepository
from chorus.repositories.task_steps import TaskStepRow, TaskStepsRepository
from chorus.repositories.trace import TraceRow, TraceRepository
from chorus.tests._helpers import fresh_conn


def _columns(conn: ConnectionFactory, table: str) -> set[str]:
    rows = conn.get().execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def test_row_fields_match_table_columns():
    conn = fresh_conn()
    # 各 repo 构造器 ensure_schema 建表
    SessionRepository(conn)
    MessageRepository(conn)
    TraceRepository(conn)
    TaskRepository(conn)
    TaskArtifactsRepository(conn)
    TaskStepsRepository(conn)

    cases = [
        ("messages", MessageRow),
        ("traces", TraceRow),
        ("tasks", TaskRow),
        ("task_artifacts", TaskArtifactsRow),
        ("task_steps", TaskStepRow),
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
