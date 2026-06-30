"""task_steps 表的唯一 SQL 入口（1:N 关联 tasks，每轮 ReAct 一行）。

供角色详情页 TaskProcess.vue 渲染创作过程（思考/工具/结果）。与 traces 分工：
task_steps = 结构化叙事（面向用户）；traces = 扁平调试遥测（开发者）。
哑查询，永不开事务。重跑从 MAX(iteration)+1 续接，保留历史轮次。

映射归框架（命名绑定 + model_fields 派生列名），形状转换（tool_calls/tool_results
json / created_at TEXT↔float）集中在 TaskStepRow.from_values / to_domain。
append 收原语（签名不变），内部生成 id/created_at，故用 from_values 而非 from_domain。
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import TaskStep
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS task_steps (
    id            TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    iteration     INTEGER NOT NULL,
    thinking      TEXT,
    text          TEXT,
    tool_calls    TEXT,
    tool_results  TEXT,
    finish_reason TEXT,
    created_at    TEXT NOT NULL,
    UNIQUE(task_id, iteration)
);
CREATE INDEX IF NOT EXISTS idx_task_steps_task ON task_steps(task_id, iteration);
"""


class TaskStepRow(BaseModel):
    """task_steps 表持久化形状（1:1 贴列）。映射归框架，转换归 from_values/to_domain。

    created_at 物理列是 TEXT（存 str(time())），Row 诚实贴 str，to_domain 里 float()。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    task_id: str
    iteration: int
    thinking: Optional[str] = None
    text: Optional[str] = None
    tool_calls: Optional[str] = None
    tool_results: Optional[str] = None
    finish_reason: Optional[str] = None
    created_at: str

    def to_domain(self) -> TaskStep:
        return TaskStep(
            id=self.id,
            task_id=self.task_id,
            iteration=self.iteration,
            thinking=self.thinking,
            text=self.text,
            tool_calls=json.loads(self.tool_calls) if self.tool_calls else None,
            tool_results=json.loads(self.tool_results) if self.tool_results else None,
            finish_reason=self.finish_reason,
            created_at=float(self.created_at) if self.created_at else 0.0,
        )

    @classmethod
    def from_values(
        cls, task_id: str, iteration: int, thinking: Optional[str], text: Optional[str],
        tool_calls: Optional[list[dict]], tool_results: Optional[list[dict]],
        finish_reason: Optional[str],
    ) -> "TaskStepRow":
        """原语 → Row（签名与 append 对齐）。内部生成 id/created_at。"""
        return cls(
            id=uuid.uuid4().hex,
            task_id=task_id,
            iteration=iteration,
            thinking=thinking,
            text=text,
            tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            tool_results=json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
            finish_reason=finish_reason,
            created_at=str(time.time()),
        )


_COLS = ", ".join(TaskStepRow.model_fields)
_PH = ", ".join(f":{k}" for k in TaskStepRow.model_fields)


class TaskStepsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(
        self, task_id: str, iteration: int, thinking: Optional[str], text: Optional[str],
        tool_calls: Optional[list[dict]], tool_results: Optional[list[dict]],
        finish_reason: Optional[str],
    ) -> None:
        row = TaskStepRow.from_values(
            task_id, iteration, thinking, text, tool_calls, tool_results, finish_reason
        )
        self._conn.get().execute(
            f"INSERT INTO task_steps({_COLS}) VALUES ({_PH})", row.model_dump()
        )

    def list_by_task(self, task_id: str) -> list[TaskStep]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM task_steps WHERE task_id=? ORDER BY iteration",
            (task_id,),
        ).fetchall()
        return [TaskStepRow(**dict(r)).to_domain() for r in rows]

    def next_iteration(self, task_id: str) -> int:
        row = self._conn.get().execute(
            "SELECT COALESCE(MAX(iteration), 0) + 1 FROM task_steps WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return int(row[0]) if row else 1
