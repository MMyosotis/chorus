"""进度快照表唯一 SQL 入口：一任务一行，upsert 覆盖，哑查询不开事务。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task.progress import TaskProgress
from chorus.repo.connection import ConnectionFactory


_DDL = """
CREATE TABLE IF NOT EXISTS task_progress (
    task_id          TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    composing_chars  INTEGER NOT NULL DEFAULT 0,
    composing_units  INTEGER NOT NULL DEFAULT 0,
    composing_label  TEXT NOT NULL DEFAULT '',
    last_signal      TEXT NOT NULL DEFAULT '',
    aside            TEXT NOT NULL DEFAULT ''
);
"""


class TaskProgressRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    task_id: str
    composing_chars: int = 0
    composing_units: int = 0
    composing_label: str = ""
    last_signal: str = ""
    aside: str = ""


class TaskProgressRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def set_composing(self, task_id: str, chars: int, units: int) -> None:
        """覆盖正文量与结构单元数。"""
        self._conn.get().execute(
            "INSERT INTO task_progress(task_id, composing_chars, composing_units) "
            "VALUES(?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            "composing_chars=excluded.composing_chars, "
            "composing_units=excluded.composing_units",
            (task_id, chars, units),
        )

    def set_composing_label(self, task_id: str, label: str) -> None:
        """覆盖单位标签。"""
        self._conn.get().execute(
            "INSERT INTO task_progress(task_id, composing_label) VALUES(?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            "composing_label=excluded.composing_label",
            (task_id, label),
        )

    def set_aside(self, task_id: str, aside: str) -> None:
        """覆盖意图旁白。"""
        self._conn.get().execute(
            "INSERT INTO task_progress(task_id, aside) VALUES(?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET aside=excluded.aside",
            (task_id, aside),
        )

    def set_signal(self, task_id: str, signal: str) -> None:
        """覆盖临时信号（纠错提示或失败标记）。"""
        self._conn.get().execute(
            "INSERT INTO task_progress(task_id, last_signal) VALUES(?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET last_signal=excluded.last_signal",
            (task_id, signal),
        )

    def load(self, task_id: str) -> Optional[TaskProgress]:
        row = self._conn.get().execute(
            "SELECT task_id, composing_chars, composing_units, "
            "composing_label, last_signal, aside "
            "FROM task_progress WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return TaskProgress(**dict(row)) if row else None

    def load_many(self, task_ids: list[str]) -> dict[str, TaskProgress]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            "SELECT task_id, composing_chars, composing_units, "
            "composing_label, last_signal, aside "
            f"FROM task_progress WHERE task_id IN ({placeholders})",
            tuple(task_ids),
        ).fetchall()
        return {row["task_id"]: TaskProgress(**dict(row)) for row in rows}
