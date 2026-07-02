"""任务产物表的唯一 SQL 入口，存产物与角色话术两个 JSON 列，哑查询不开事务。

映射归框架，转换集中在行模型。upsert 收原语不收领域对象。
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskArtifacts
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_artifacts (
    task_id     TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    artifacts   TEXT,
    narrative   TEXT,
    updated_at  REAL
);
"""


class TaskArtifactsRow(BaseModel):
    """任务产物表持久化形状，与列一一对应。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    task_id: str
    artifacts: Optional[str] = None
    narrative: Optional[str] = None
    updated_at: Optional[float] = None

    def to_domain(self) -> TaskArtifacts:
        return TaskArtifacts(
            task_id=self.task_id,
            artifacts=json.loads(self.artifacts) if self.artifacts else None,
            narrative=json.loads(self.narrative) if self.narrative else None,
        )

    @classmethod
    def from_values(
        cls, task_id: str, artifacts: Any, narrative: Any, updated_at: Optional[float] = None,
    ) -> "TaskArtifactsRow":
        """原语转行模型，话术允许为空。"""
        return cls(
            task_id=task_id,
            artifacts=json.dumps(artifacts, ensure_ascii=False) if artifacts is not None else None,
            narrative=json.dumps(narrative, ensure_ascii=False) if narrative is not None else None,
            updated_at=updated_at,
        )


_COLS = ", ".join(TaskArtifactsRow.model_fields)
_PH = ", ".join(f":{k}" for k in TaskArtifactsRow.model_fields)


class TaskArtifactsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """幂等加列，建表语句不覆盖旧表。"""
        cols = {
            row["name"]
            for row in self._conn.get().execute("PRAGMA table_info(task_artifacts)").fetchall()
        }
        if "updated_at" not in cols:
            self._conn.get().execute("ALTER TABLE task_artifacts ADD COLUMN updated_at REAL")

    def upsert(
        self, task_id: str, artifacts: Any, narrative: Any
    ) -> None:
        row = TaskArtifactsRow.from_values(task_id, artifacts, narrative, time.time())
        self._conn.get().execute(
            f"INSERT INTO task_artifacts({_COLS}) VALUES ({_PH}) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            "artifacts=excluded.artifacts, narrative=excluded.narrative, updated_at=excluded.updated_at",
            row.model_dump(),
        )

    def load(self, task_id: str) -> Optional[TaskArtifacts]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_artifacts WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return TaskArtifactsRow(**dict(row)).to_domain() if row else None

    def load_many(self, task_ids: list[str]) -> dict[str, TaskArtifacts]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_artifacts "
            f"WHERE task_id IN ({placeholders})",
            tuple(task_ids),
        ).fetchall()
        return {r["task_id"]: TaskArtifactsRow(**dict(r)).to_domain() for r in rows}
