# kitty/repositories/task_artifacts.py
"""task_artifacts 表的唯一 SQL 入口（1:1 关联 tasks，大 JSON 产物）。

step_output（下游注入用）/ artifacts（前端渲染用，= step_output 同值）/ narrative
（角色话术）三个 JSON 列。哑查询，永不开事务（与 cas_update 同事务由 service 拼）。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from chorus.domain.task import TaskArtifacts
from chorus.repositories.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_artifacts (
    task_id     TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    step_output TEXT,
    artifacts   TEXT,
    narrative   TEXT
);
"""


class TaskArtifactsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def upsert(
        self, task_id: str, step_output: Any, artifacts: Any, narrative: Any
    ) -> None:
        self._conn.get().execute(
            "INSERT INTO task_artifacts(task_id, step_output, artifacts, narrative) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            "step_output=excluded.step_output, artifacts=excluded.artifacts, narrative=excluded.narrative",
            (
                task_id,
                json.dumps(step_output, ensure_ascii=False),
                json.dumps(artifacts, ensure_ascii=False),
                json.dumps(narrative, ensure_ascii=False) if narrative is not None else None,
            ),
        )

    def load(self, task_id: str) -> Optional[TaskArtifacts]:
        row = self._conn.get().execute(
            "SELECT task_id, step_output, artifacts, narrative FROM task_artifacts WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return self._row_to_artifacts(row) if row else None

    def load_many(self, task_ids: list[str]) -> dict[str, TaskArtifacts]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT task_id, step_output, artifacts, narrative FROM task_artifacts "
            f"WHERE task_id IN ({placeholders})",
            tuple(task_ids),
        ).fetchall()
        return {r[0]: self._row_to_artifacts(r) for r in rows}

    @staticmethod
    def _row_to_artifacts(row) -> TaskArtifacts:
        tid, so, art, nar = row
        return TaskArtifacts(
            task_id=tid,
            step_output=json.loads(so) if so else None,
            artifacts=json.loads(art) if art else None,
            narrative=json.loads(nar) if nar else None,
        )
