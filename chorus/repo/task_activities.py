"""活动流表的唯一 SQL 入口，按事件粒度追加，哑查询不开事务。

映射归框架，多个 JSON 列的转换集中在行模型。追加收原语，标识与时间在内部生成。
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskActivity
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_activities (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id               TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    event_type            TEXT NOT NULL,
    tool_name             TEXT,
    tool_call_id          TEXT,
    role_line             TEXT NOT NULL,
    detail_md             TEXT,
    summary_json          TEXT,
    progress_json         TEXT,
    artifact_preview_json TEXT,
    status                TEXT NOT NULL,
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_activities_task_id
ON task_activities(task_id, id);
CREATE INDEX IF NOT EXISTS idx_task_activities_task_updated
ON task_activities(task_id, updated_at);
"""


class TaskActivityRow(BaseModel):
    """活动流表持久化形状，与列一一对应。主键自增，插入后回读。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: Optional[int] = None
    task_id: str
    event_type: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    role_line: str
    detail_md: Optional[str] = None
    summary_json: Optional[str] = None
    progress_json: Optional[str] = None
    artifact_preview_json: Optional[str] = None
    status: str
    created_at: float
    updated_at: float

    def to_domain(self) -> TaskActivity:
        return TaskActivity(
            id=self.id, task_id=self.task_id,
            event_type=self.event_type,
            tool_name=self.tool_name, tool_call_id=self.tool_call_id,
            role_line=self.role_line, detail_md=self.detail_md,
            summary_json=_loads(self.summary_json),
            progress_json=_loads(self.progress_json),
            artifact_preview_json=_loads(self.artifact_preview_json),
            status=self.status, created_at=self.created_at, updated_at=self.updated_at,
        )

    @classmethod
    def from_values(
        cls, task_id: str, event_type: str,
        role_line: str, status: str, now: float,
        *, tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        detail_md: Optional[str] = None, summary_json: Any = None,
        progress_json: Any = None, artifact_preview_json: Any = None,
        updated_at: Optional[float] = None,
    ) -> "TaskActivityRow":
        return cls(
            id=None, task_id=task_id,
            event_type=event_type, tool_name=tool_name,
            tool_call_id=tool_call_id, role_line=role_line,
            detail_md=detail_md,
            summary_json=json.dumps(summary_json, ensure_ascii=False) if summary_json is not None else None,
            progress_json=json.dumps(progress_json, ensure_ascii=False) if progress_json is not None else None,
            artifact_preview_json=json.dumps(artifact_preview_json, ensure_ascii=False) if artifact_preview_json is not None else None,
            status=status, created_at=now, updated_at=updated_at if updated_at is not None else now,
        )


def _loads(raw: Optional[str]) -> Any:
    return json.loads(raw) if raw else None


# 插入排除自增主键，由库分配后回读
_INSERT_COLS = ", ".join(k for k in TaskActivityRow.model_fields if k != "id")
_INSERT_PH = ", ".join(f":{k}" for k in TaskActivityRow.model_fields if k != "id")
_SELECT_COLS = ", ".join(TaskActivityRow.model_fields)


class TaskActivitiesRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(
        self, task_id: str, event_type: str, role_line: str,
        status: str = "running", *,
        tool_name: Optional[str] = None, tool_call_id: Optional[str] = None,
        detail_md: Optional[str] = None,
        summary_json: Any = None, progress_json: Any = None,
        artifact_preview_json: Any = None, updated_at: Optional[float] = None,
    ) -> TaskActivity:
        now = updated_at if updated_at is not None else time.time()
        row = TaskActivityRow.from_values(
            task_id, event_type, role_line, status, now,
            tool_name=tool_name, tool_call_id=tool_call_id,
            detail_md=detail_md, summary_json=summary_json,
            progress_json=progress_json, artifact_preview_json=artifact_preview_json,
            updated_at=updated_at,
        )
        cur = self._conn.get().execute(
            f"INSERT INTO task_activities({_INSERT_COLS}) VALUES ({_INSERT_PH})",
            row.model_dump(exclude={"id"}),
        )
        # 自增主键由库分配，回读注入行模型
        return row.model_copy(update={"id": int(cur.lastrowid)}).to_domain()

    def list_by_task(self, task_id: str, *, limit: int = 50) -> list[TaskActivity]:
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities "
            "WHERE task_id=? ORDER BY id LIMIT ?",
            (task_id, limit),
        ).fetchall()
        return [TaskActivityRow(**dict(r)).to_domain() for r in rows]

    def latest_by_task(self, task_id: str) -> Optional[TaskActivity]:
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities "
            "WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchall()
        return TaskActivityRow(**dict(rows[0])).to_domain() if rows else None

    def latest_by_tasks(self, task_ids: list[str]) -> dict[str, TaskActivity]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT {_SELECT_COLS} FROM task_activities a JOIN ("
            f"SELECT task_id AS t_id, MAX(id) AS max_id FROM task_activities "
            f"WHERE task_id IN ({placeholders}) GROUP BY task_id"
            f") x ON a.task_id = x.t_id AND a.id = x.max_id",
            tuple(task_ids),
        ).fetchall()
        return {r["task_id"]: TaskActivityRow(**dict(r)).to_domain() for r in rows}
