"""活动流表的唯一 SQL 入口，按事件粒度追加，哑查询不开事务。

载荷收敛为单个 JSON 列，按事件类型区分多态。单表单语句，零事务。
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import ActivityDraft, TaskActivity, build_payload
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_activities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    role_line   TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  REAL NOT NULL,
    tool_name   TEXT,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_activities_task_id
ON task_activities(task_id, id);
"""


class TaskActivityRow(BaseModel):
    """活动流表持久化形状，与列一一对应。载荷为 JSON 列。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: Optional[int] = None
    task_id: str
    event_type: str
    role_line: str
    status: str
    created_at: float
    tool_name: Optional[str] = None
    payload: Optional[str] = None

    def to_domain(self) -> TaskActivity:
        data = json.loads(self.payload) if self.payload else None
        return TaskActivity(
            id=self.id, task_id=self.task_id,
            event_type=self.event_type, role_line=self.role_line,
            status=self.status, created_at=self.created_at,
            tool_name=self.tool_name,
            payload=build_payload(self.event_type, self.tool_name, data),
        )

    @classmethod
    def from_domain(
        cls, task_id: str, draft: ActivityDraft, created_at: float,
    ) -> "TaskActivityRow":
        """领域草稿转行模型，载荷经 JSON 序列化。"""
        return cls(
            id=None, task_id=task_id,
            event_type=draft.event_type, role_line=draft.role_line,
            status=draft.status, created_at=created_at,
            tool_name=draft.tool_name,
            payload=json.dumps(asdict(draft.payload), ensure_ascii=False)
            if draft.payload is not None else None,
        )


_INSERT_COLS = ", ".join(field for field in TaskActivityRow.model_fields if field != "id")
_INSERT_PH = ", ".join(f":{field}" for field in TaskActivityRow.model_fields if field != "id")
_SELECT_COLS = ", ".join(TaskActivityRow.model_fields)


class TaskActivitiesRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(self, task_id: str, draft: ActivityDraft) -> TaskActivity:
        row = TaskActivityRow.from_domain(task_id, draft, time.time())
        cur = self._conn.get().execute(
            f"INSERT INTO task_activities({_INSERT_COLS}) VALUES ({_INSERT_PH})",
            row.model_dump(exclude={"id"}),
        )
        return row.model_copy(update={"id": int(cur.lastrowid)}).to_domain()

    def list_by_task(self, task_id: str, *, limit: int = 50) -> list[TaskActivity]:
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities "
            "WHERE task_id=? ORDER BY id LIMIT ?",
            (task_id, limit),
        ).fetchall()
        return [TaskActivityRow(**dict(row)).to_domain() for row in rows]

    def latest_by_task(self, task_id: str) -> Optional[TaskActivity]:
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities "
            "WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchall()
        return TaskActivityRow(**dict(rows[0])).to_domain() if rows else None

    def latest_by_tasks(self, task_ids: list[str]) -> dict[str, TaskActivity]:
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities a JOIN ("
            f"SELECT task_id AS t_id, MAX(id) AS max_id FROM task_activities "
            f"WHERE task_id IN ({placeholders}) GROUP BY task_id"
            f") x ON a.task_id = x.t_id AND a.id = x.max_id",
            tuple(task_ids),
        ).fetchall()
        return {row["task_id"]: TaskActivityRow(**dict(row)).to_domain() for row in rows}
