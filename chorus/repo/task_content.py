"""任务内容表的唯一 SQL 入口，与任务表一一对应，哑查询不开事务。

跨表原子写由编排层开事务，本层只提供原语。
"""
from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskContent
from chorus.repo.connection import ConnectionFactory
from chorus.repo.mapping import shared_fields

_DDL = """
CREATE TABLE IF NOT EXISTS task_content (
    task_id        TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    invoke_message TEXT NOT NULL,
    progress_total INTEGER,
    error          TEXT,
    feedback       TEXT
);
"""


class TaskContentRow(BaseModel):
    """任务内容表持久化形状，与列一一对应。错误与反馈均为纯文本。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    task_id: str
    invoke_message: str
    progress_total: Optional[int] = None
    error: Optional[str] = None
    feedback: Optional[str] = None

    def to_domain(self) -> TaskContent:
        return TaskContent(**shared_fields(self, TaskContent))

    @classmethod
    def from_domain(cls, content: TaskContent) -> "TaskContentRow":
        return cls(**shared_fields(content, cls))


_COLS = ", ".join(TaskContentRow.model_fields)
_PH = ", ".join(f":{field}" for field in TaskContentRow.model_fields)


class TaskContentRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def insert(self, content: TaskContent) -> None:
        """建图时写入（与任务表插入同事务）。"""
        row = TaskContentRow.from_domain(content)
        self._conn.get().execute(
            f"INSERT INTO task_content({_COLS}) VALUES ({_PH})", row.model_dump()
        )

    def load(self, task_id: str) -> Optional[TaskContent]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_content WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return TaskContentRow(**dict(row)).to_domain() if row else None

    def load_many(self, task_ids: list[str]) -> dict[str, TaskContent]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_content WHERE task_id IN ({placeholders})",
            tuple(task_ids),
        ).fetchall()
        return {row["task_id"]: TaskContentRow(**dict(row)).to_domain() for row in rows}

    def set_error(self, task_id: str, error: str) -> None:
        """写错误信息，upsert（与任务表 CAS 同事务）。"""
        self._conn.get().execute(
            "INSERT INTO task_content(task_id, invoke_message, error) VALUES(?, '', ?) "
            "ON CONFLICT(task_id) DO UPDATE SET error=excluded.error",
            (task_id, error),
        )

    def set_feedback(self, task_id: str, feedback: str) -> None:
        """写反馈，upsert（与任务表 CAS 同事务）。"""
        self._conn.get().execute(
            "INSERT INTO task_content(task_id, invoke_message, feedback) VALUES(?, '', ?) "
            "ON CONFLICT(task_id) DO UPDATE SET feedback=excluded.feedback",
            (task_id, feedback),
        )
