# kitty/repo/task_activities.py
"""task_activities 表的唯一 SQL 入口（用户态活动流，1:N 关联 tasks）。

与 task_steps 分工：task_activities = 用户可见活动（按事件粒度，append 递进）；
task_steps = raw ReAct iteration（开发者/兼容期）。哑查询，永不开事务。

映射归框架（命名绑定 + model_fields 派生列名），形状转换（3×json）集中在
TaskActivityRow.from_values / to_domain。append 收原语（签名不变），内部生成
id/seq/created_at，故用 from_values 而非 from_domain。
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskActivity
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_activities (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    seq                   INTEGER NOT NULL,
    iteration             INTEGER,
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
    updated_at            REAL NOT NULL,
    UNIQUE(task_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_task_activities_task_seq
ON task_activities(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_task_activities_task_updated
ON task_activities(task_id, updated_at);
"""


class TaskActivityRow(BaseModel):
    """task_activities 表持久化形状（1:1 贴列）。映射归框架，转换归 from_values/to_domain。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    task_id: str
    seq: int
    iteration: Optional[int] = None
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
            id=self.id, task_id=self.task_id, seq=self.seq, iteration=self.iteration,
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
        cls, task_id: str, seq: int, event_type: str,
        role_line: str, status: str, now: float,
        *, iteration: Optional[int] = None, tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        detail_md: Optional[str] = None, summary_json: Any = None,
        progress_json: Any = None, artifact_preview_json: Any = None,
        updated_at: Optional[float] = None,
    ) -> "TaskActivityRow":
        return cls(
            id=uuid.uuid4().hex, task_id=task_id, seq=seq, iteration=iteration,
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


_COLS = ", ".join(TaskActivityRow.model_fields)
_PH = ", ".join(f":{k}" for k in TaskActivityRow.model_fields)


class TaskActivitiesRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def next_seq(self, task_id: str) -> int:
        row = self._conn.get().execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM task_activities WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return int(row[0]) if row else 1

    def append(
        self, task_id: str, event_type: str, role_line: str,
        status: str = "running", *, iteration: Optional[int] = None,
        tool_name: Optional[str] = None, tool_call_id: Optional[str] = None,
        detail_md: Optional[str] = None,
        summary_json: Any = None, progress_json: Any = None,
        artifact_preview_json: Any = None, updated_at: Optional[float] = None,
    ) -> TaskActivity:
        now = updated_at if updated_at is not None else time.time()
        seq = self.next_seq(task_id)
        row = TaskActivityRow.from_values(
            task_id, seq, event_type, role_line, status, now,
            iteration=iteration, tool_name=tool_name, tool_call_id=tool_call_id,
            detail_md=detail_md, summary_json=summary_json,
            progress_json=progress_json, artifact_preview_json=artifact_preview_json,
            updated_at=updated_at,
        )
        self._conn.get().execute(
            f"INSERT INTO task_activities({_COLS}) VALUES ({_PH})", row.model_dump()
        )
        return row.to_domain()

    def list_by_task(
        self, task_id: str, *, limit: int = 50, after_seq: Optional[int] = None,
    ) -> list[TaskActivity]:
        if after_seq is not None:
            rows = self._conn.get().execute(
                f"SELECT {_COLS} FROM task_activities "
                "WHERE task_id=? AND seq>? ORDER BY seq LIMIT ?",
                (task_id, after_seq, limit),
            ).fetchall()
        else:
            rows = self._conn.get().execute(
                f"SELECT {_COLS} FROM task_activities "
                "WHERE task_id=? ORDER BY seq LIMIT ?",
                (task_id, limit),
            ).fetchall()
        return [TaskActivityRow(**dict(r)).to_domain() for r in rows]

    def latest_by_task(self, task_id: str) -> Optional[TaskActivity]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_activities "
            "WHERE task_id=? ORDER BY seq DESC LIMIT 1",
            (task_id,),
        ).fetchall()
        return TaskActivityRow(**dict(rows[0])).to_domain() if rows else None

    def latest_by_tasks(self, task_ids: list[str]) -> dict[str, TaskActivity]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        rows = self._conn.get().execute(
            f"SELECT a.* FROM task_activities a JOIN ("
            f"SELECT task_id, MAX(seq) AS max_seq FROM task_activities "
            f"WHERE task_id IN ({placeholders}) GROUP BY task_id"
            f") x ON a.task_id = x.task_id AND a.seq = x.max_seq",
            tuple(task_ids),
        ).fetchall()
        return {r["task_id"]: TaskActivityRow(**dict(r)).to_domain() for r in rows}

