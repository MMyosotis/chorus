"""task_artifacts 表的唯一 SQL 入口（1:1 关联 tasks，大 JSON 产物）。

artifacts（前端渲染用 + 下游注入用，同源同值）/ narrative（角色话术）两个 JSON 列。
哑查询，永不开事务（与 cas_update 同事务由 service 拼）。

映射归框架（命名绑定 + model_fields 派生列名），形状转换（2×json）集中在
TaskArtifactsRow.from_values / to_domain。upsert 收原语（签名不变），不收领域对象，
故用 from_values 而非 from_domain。
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
    """task_artifacts 表持久化形状（1:1 贴列）。映射归框架，转换归 from_values/to_domain。"""

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
        """原语 → Row（签名与 upsert 对齐，不收领域对象）。narrative 允许 None。"""
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
        """幂等加列（无迁移框架，CREATE TABLE IF NOT EXISTS 不覆盖已存在的旧表）。"""
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
