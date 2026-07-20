"""任务产物表的唯一 SQL 入口：存产物 JSON，读写都经行模型在裸数据和
领域对象间互转。每行自带角色，读回时按角色还原成对应的产物对象。
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskArtifacts
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_artifacts (
    task_id     TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    agent_type  TEXT NOT NULL,
    artifacts   TEXT NOT NULL
);
"""


class TaskArtifactsRow(BaseModel):
    """任务产物表持久化形状，与列一一对应。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    task_id: str
    agent_type: str
    artifacts: str

    def to_domain(self) -> TaskArtifacts:
        """按本行角色类型用注册表里的模型把 JSON 还原成强类型产物。"""
        artifacts = AGENT_PROFILES[self.agent_type].build_artifacts(json.loads(self.artifacts))
        return TaskArtifacts(task_id=self.task_id, artifacts=artifacts)

    @classmethod
    def from_domain(
        cls, task_id: str, agent_type: str, artifacts: Any,
    ) -> "TaskArtifactsRow":
        """领域对象转行模型。"""
        return cls(
            task_id=task_id, agent_type=agent_type,
            artifacts=json.dumps(dataclasses.asdict(artifacts), ensure_ascii=False),
        )


_COLS = ", ".join(TaskArtifactsRow.model_fields)
_PH = ", ".join(f":{field}" for field in TaskArtifactsRow.model_fields)


class TaskArtifactsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def upsert(
        self, task_id: str, agent_type: str, artifacts: Any,
    ) -> None:
        row = TaskArtifactsRow.from_domain(task_id, agent_type, artifacts)
        self._conn.get().execute(
            f"INSERT INTO task_artifacts({_COLS}) VALUES ({_PH}) "
            "ON CONFLICT(task_id) DO UPDATE SET "
            "agent_type=excluded.agent_type, "
            "artifacts=excluded.artifacts",
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
        return {row["task_id"]: TaskArtifactsRow(**dict(row)).to_domain() for row in rows}
