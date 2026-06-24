# kitty/repositories/task.py
"""tasks 表的唯一 SQL 入口（哑查询，永不开事务，无业务规则）。

表结构见 spec 3.1。CAS 合法性分工：domain 出 LEGAL_TRANSITIONS 规则表；service 方法
结构性只做一条合法翻转；repo cas_update 仅原子原语（WHERE status=from 看 rowcount），
不管翻转合不合法。状态集合由 service 从 domain 传入（WHERE status IN ?），repo 不硬编码。
"""
from __future__ import annotations

import json
import time
from typing import Iterable, Optional

from kitty.domain.task import Task
from kitty.repositories.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL,
    pipeline_id    TEXT NOT NULL,
    agent_type     TEXT NOT NULL,
    seq            INTEGER NOT NULL,
    status         TEXT NOT NULL,
    invoke_message TEXT NOT NULL,
    dependencies   TEXT NOT NULL DEFAULT '[]',
    feedback       TEXT,
    error          TEXT,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
"""

# cas_update 允许顺带更新的字段（白名单，防 SQL 注入与误写）
_CAS_FIELDS = {"error", "feedback", "updated_at"}


class TaskRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def insert(self, task: Task) -> None:
        self._conn.get().execute(
            "INSERT INTO tasks(id, session_id, pipeline_id, agent_type, seq, status, "
            "invoke_message, dependencies, feedback, error, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task.id, task.session_id, task.pipeline_id, task.agent_type, task.seq,
                task.status, task.invoke_message,
                json.dumps(task.dependencies, ensure_ascii=False),
                json.dumps(task.feedback, ensure_ascii=False) if task.feedback is not None else None,
                task.error, task.created_at, task.updated_at,
            ),
        )

    def get(self, task_id: str) -> Optional[Task]:
        row = self._conn.get().execute(
            "SELECT id, session_id, pipeline_id, agent_type, seq, status, invoke_message, "
            "dependencies, feedback, error, created_at, updated_at FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return self._row_to_task(row) if row else None

    def cas_update(
        self, task_id: str, from_status: str, to_status: str, **fields
    ) -> bool:
        """原子原语：UPDATE ... WHERE id=? AND status=from_status，看 rowcount。
        不管翻转合不合法（合法性由 domain LEGAL_TRANSITIONS + service 保证）。
        **fields 仅允许 error/feedback/updated_at。
        """
        bad = set(fields) - _CAS_FIELDS
        if bad:
            raise ValueError(f"cas_update 不允许字段: {bad}")
        sets = ["status=?", "updated_at=?"]
        params: list[object] = [to_status, fields.get("updated_at", time.time())]
        for f in ("error", "feedback"):
            if f in fields:
                sets.append(f"{f}=?")
                val = fields[f]
                params.append(json.dumps(val, ensure_ascii=False) if f == "feedback" and val is not None else val)
        params.extend([task_id, from_status])
        cur = self._conn.get().execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id=? AND status=?", params
        )
        return cur.rowcount > 0

    def cancel_pipeline(self, pipeline_id: str) -> int:
        """事务内批量 CAS 非终态 task→cancelled。返受影响行数。"""
        statuses = ("pending", "running", "awaiting_confirm")
        placeholders = ",".join("?" * len(statuses))
        with self._conn.transaction():
            cur = self._conn.get().execute(
                f"UPDATE tasks SET status='cancelled', updated_at=? "
                f"WHERE pipeline_id=? AND status IN ({placeholders})",
                (time.time(), pipeline_id, *statuses),
            )
            return cur.rowcount

    def find_pending_with_deps(self) -> list[tuple[Task, list[Task]]]:
        """返所有 pending task + 其 deps 行（哑查询，调度判定交 domain can_schedule）。"""
        pending_rows = self._conn.get().execute(
            "SELECT id, session_id, pipeline_id, agent_type, seq, status, invoke_message, "
            "dependencies, feedback, error, created_at, updated_at FROM tasks WHERE status='pending'"
        ).fetchall()
        result: list[tuple[Task, list[Task]]] = []
        for row in pending_rows:
            task = self._row_to_task(row)
            deps = [self.get(d) for d in task.dependencies if d]
            result.append((task, [d for d in deps if d is not None]))
        return result

    def find_running_before(self, cutoff_ts: float) -> list[Task]:
        rows = self._conn.get().execute(
            "SELECT id, session_id, pipeline_id, agent_type, seq, status, invoke_message, "
            "dependencies, feedback, error, created_at, updated_at FROM tasks "
            "WHERE status='running' AND updated_at < ?",
            (cutoff_ts,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def find_by_session_statuses(
        self, session_id: str, statuses: Iterable[str]
    ) -> list[Task]:
        statuses = list(statuses)
        if not statuses:
            return []
        placeholders = ",".join("?" * len(statuses))
        rows = self._conn.get().execute(
            f"SELECT id, session_id, pipeline_id, agent_type, seq, status, invoke_message, "
            f"dependencies, feedback, error, created_at, updated_at FROM tasks "
            f"WHERE session_id=? AND status IN ({placeholders}) ORDER BY seq",
            (session_id, *statuses),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def count_by_session_statuses(
        self, session_id: str, statuses: Iterable[str]
    ) -> int:
        statuses = list(statuses)
        if not statuses:
            return 0
        placeholders = ",".join("?" * len(statuses))
        row = self._conn.get().execute(
            f"SELECT COUNT(*) FROM tasks WHERE session_id=? AND status IN ({placeholders})",
            (session_id, *statuses),
        ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row_to_task(row) -> Task:
        (tid, sid, pid, at, seq, status, invoke, deps_json, fb_json, err,
         created, updated) = row
        try:
            deps = json.loads(deps_json) if deps_json else []
        except json.JSONDecodeError:
            deps = []
        try:
            feedback = json.loads(fb_json) if fb_json else None
        except json.JSONDecodeError:
            feedback = None
        return Task(
            id=tid, session_id=sid, pipeline_id=pid, agent_type=at, seq=seq,
            status=status, invoke_message=invoke, dependencies=deps,
            feedback=feedback, error=err, created_at=created, updated_at=updated,
        )
