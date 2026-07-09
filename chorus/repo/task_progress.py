"""进度快照表唯一 SQL 入口：一任务一行，upsert 覆盖，哑查询不开事务。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task.activity import TaskProgress
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

    def upsert_progress(
        self, task_id: str, *,
        composing_chars: Optional[int] = None,
        composing_units: Optional[int] = None,
        composing_label: Optional[str] = None,
        last_signal: Optional[str] = None,
        aside: Optional[str] = None,
    ) -> None:
        """覆盖更新非 None 字段,不存在则插入。"""
        cols: list[str] = []
        params: list = [task_id]
        for col, val in [
            ("composing_chars", composing_chars),
            ("composing_units", composing_units),
            ("composing_label", composing_label),
            ("last_signal", last_signal),
            ("aside", aside),
        ]:
            if val is not None:
                cols.append(col)
                params.append(val)
        if not cols:
            return
        all_cols = ", ".join(["task_id"] + cols)
        placeholders = ", ".join("?" * (1 + len(cols)))
        set_clause = ", ".join(f"{col}=excluded.{col}" for col in cols)
        self._conn.get().execute(
            f"INSERT INTO task_progress({all_cols}) VALUES({placeholders}) "
            f"ON CONFLICT(task_id) DO UPDATE SET {set_clause}",
            params,
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
