# kitty/repositories/task_steps.py
"""task_steps 表的唯一 SQL 入口（1:N 关联 tasks，每轮 ReAct 一行）。

供角色详情页 TaskProcess.vue 渲染创作过程（思考/工具/结果）。与 traces 分工：
task_steps = 结构化叙事（面向用户）；traces = 扁平调试遥测（开发者）。
哑查询，永不开事务。重跑从 MAX(iteration)+1 续接，保留历史轮次。
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from kitty.domain.task import TaskStep
from kitty.repositories.connection import ConnectionFactory

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


class TaskStepsRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def append(
        self, task_id: str, iteration: int, thinking: Optional[str], text: Optional[str],
        tool_calls: Optional[list[dict]], tool_results: Optional[list[dict]],
        finish_reason: Optional[str],
    ) -> None:
        self._conn.get().execute(
            "INSERT INTO task_steps(id, task_id, iteration, thinking, text, "
            "tool_calls, tool_results, finish_reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex, task_id, iteration, thinking, text,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
                finish_reason, time.time(),
            ),
        )

    def list_by_task(self, task_id: str) -> list[TaskStep]:
        rows = self._conn.get().execute(
            "SELECT id, task_id, iteration, thinking, text, tool_calls, tool_results, "
            "finish_reason, created_at FROM task_steps WHERE task_id=? ORDER BY iteration",
            (task_id,),
        ).fetchall()
        return [self._row_to_step(r) for r in rows]

    def next_iteration(self, task_id: str) -> int:
        row = self._conn.get().execute(
            "SELECT COALESCE(MAX(iteration), 0) + 1 FROM task_steps WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return int(row[0]) if row else 1

    @staticmethod
    def _row_to_step(row) -> TaskStep:
        sid, tid, it, think, text, tc, tr, fr, created = row
        return TaskStep(
            id=sid, task_id=tid, iteration=it, thinking=think, text=text,
            tool_calls=json.loads(tc) if tc else None,
            tool_results=json.loads(tr) if tr else None,
            finish_reason=fr, created_at=float(created) if created else 0.0,
        )
