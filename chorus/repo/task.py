"""任务表的唯一 SQL 入口，哑查询不开事务。

只存调度+身份+状态机；内容字段见 task_content。状态集合由编排层传入，不硬编码。
"""
from __future__ import annotations

import json
import time
from typing import Iterable, Optional

from pydantic import BaseModel, ConfigDict

from chorus.domain.task import Task
from chorus.repo.connection import ConnectionFactory

_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL,
    pipeline_id    TEXT NOT NULL,
    agent_type     TEXT NOT NULL,
    status         TEXT NOT NULL,
    dependencies   TEXT NOT NULL DEFAULT '[]',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    owner_id       REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
"""

class TaskRow(BaseModel):
    """任务表持久化形状，与列一一对应。依赖为 JSON 列。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    session_id: str
    pipeline_id: str
    agent_type: str
    status: str
    dependencies: str
    created_at: float
    updated_at: float
    owner_id: Optional[float] = None

    def to_domain(self) -> Task:
        try:
            deps = json.loads(self.dependencies) if self.dependencies else []
        except json.JSONDecodeError:
            deps = []
        return Task(
            id=self.id, session_id=self.session_id, pipeline_id=self.pipeline_id,
            agent_type=self.agent_type, status=self.status,
            dependencies=deps,
            created_at=self.created_at, updated_at=self.updated_at,
            owner_id=self.owner_id,
        )

    @classmethod
    def from_domain(cls, task: Task) -> "TaskRow":
        return cls(
            id=task.id, session_id=task.session_id, pipeline_id=task.pipeline_id,
            agent_type=task.agent_type, status=task.status,
            dependencies=json.dumps(task.dependencies, ensure_ascii=False),
            created_at=task.created_at, updated_at=task.updated_at,
            owner_id=task.owner_id,
        )


_COLS = ", ".join(TaskRow.model_fields)
_PH = ", ".join(f":{k}" for k in TaskRow.model_fields)


class TaskRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)

    def insert(self, task: Task) -> None:
        row = TaskRow.from_domain(task)
        self._conn.get().execute(
            f"INSERT INTO tasks({_COLS}) VALUES ({_PH})", row.model_dump()
        )

    def get(self, task_id: str) -> Optional[Task]:
        row = self._conn.get().execute(
            f"SELECT {_COLS} FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        return TaskRow(**dict(row)).to_domain() if row else None

    def transition(self, task_id: str, from_status: str, to_status: str) -> bool:
        """原子状态翻转：据原状态匹配更新，看影响行数。updated_at 自动刷新。"""
        cur = self._conn.get().execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=? AND status=?",
            (to_status, time.time(), task_id, from_status),
        )
        return cur.rowcount > 0

    def claim(self, task_id: str, now: float) -> bool:
        """scheduler 派发占槽：pending→running，顺带写 owner_id 与 updated_at（同戳）。"""
        cur = self._conn.get().execute(
            "UPDATE tasks SET status='running', owner_id=?, updated_at=? "
            "WHERE id=? AND status='pending'",
            (now, now, task_id),
        )
        return cur.rowcount > 0

    def touch_updated_at(self, task_id: str) -> None:
        """心跳：直接更新时间，不走翻转不校验状态，防僵死误杀。"""
        self._conn.get().execute(
            "UPDATE tasks SET updated_at=? WHERE id=?", (time.time(), task_id)
        )

    def cancel_pipeline(self, pipeline_id: str, statuses: Iterable[str]) -> int:
        """事务内批量取消非终态任务，返回受影响行数。状态集合由编排层传入。"""
        statuses = list(statuses)
        placeholders = ",".join("?" * len(statuses))
        now = time.time()
        with self._conn.transaction():
            cur = self._conn.get().execute(
                f"UPDATE tasks SET status='cancelled', updated_at=? "
                f"WHERE pipeline_id=? AND status IN ({placeholders})",
                (now, pipeline_id, *statuses),
            )
            return cur.rowcount

    def find_pending_with_deps(self) -> list[tuple[Task, list[Task]]]:
        """返回所有待执行任务及其依赖，调度判定交领域。"""
        pending_rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM tasks WHERE status='pending'"
        ).fetchall()
        result: list[tuple[Task, list[Task]]] = []
        for row in pending_rows:
            task = TaskRow(**dict(row)).to_domain()
            deps = [self.get(d) for d in task.dependencies if d]
            result.append((task, [d for d in deps if d is not None]))
        return result

    def find_running_before(self, cutoff_ts: float) -> list[Task]:
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM tasks "
            "WHERE status='running' AND updated_at < ?",
            (cutoff_ts,),
        ).fetchall()
        return [TaskRow(**dict(r)).to_domain() for r in rows]

    def find_by_session_statuses(
        self, session_id: str, statuses: Iterable[str]
    ) -> list[Task]:
        statuses = list(statuses)
        placeholders = ",".join("?" * len(statuses))
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM tasks "
            f"WHERE session_id=? AND status IN ({placeholders}) ORDER BY created_at, id",
            (session_id, *statuses),
        ).fetchall()
        return [TaskRow(**dict(r)).to_domain() for r in rows]

    def find_by_pipeline(self, pipeline_id: str) -> list[Task]:
        """返回流水线全部任务按创建升序，展示用拓扑序由编排层排。"""
        rows = self._conn.get().execute(
            f"SELECT {_COLS} FROM tasks WHERE pipeline_id=? ORDER BY created_at, id",
            (pipeline_id,),
        ).fetchall()
        return [TaskRow(**dict(r)).to_domain() for r in rows]

    def count_by_session_statuses(
        self, session_id: str, statuses: Iterable[str]
    ) -> int:
        statuses = list(statuses)
        placeholders = ",".join("?" * len(statuses))
        row = self._conn.get().execute(
            f"SELECT COUNT(*) FROM tasks WHERE session_id=? AND status IN ({placeholders})",
            (session_id, *statuses),
        ).fetchone()
        return int(row[0]) if row else 0
