"""任务表的唯一 SQL 入口，哑查询不开事务。

状态翻转合法性由领域规则与编排层把关，仓储只做原子原语；状态集合由编排层传入，不在本层硬编码。
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
    invoke_message TEXT NOT NULL,
    dependencies   TEXT NOT NULL DEFAULT '[]',
    feedback       TEXT,
    error          TEXT,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    started_at     REAL,
    finished_at    REAL,
    progress_total INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
"""

# 状态翻转时允许顺带更新的字段白名单
_CAS_FIELDS = {"error", "feedback", "updated_at", "started_at", "finished_at"}
# 配图总数建图期一次写入，运行期不可变，不进翻转


class TaskRow(BaseModel):
    """任务表持久化形状，与列一一对应。依赖与反馈为 JSON 列。"""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    session_id: str
    pipeline_id: str
    agent_type: str
    status: str
    invoke_message: str
    dependencies: str
    feedback: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress_total: Optional[int] = None

    def to_domain(self) -> Task:
        try:
            deps = json.loads(self.dependencies) if self.dependencies else []
        except json.JSONDecodeError:
            deps = []
        try:
            feedback = json.loads(self.feedback) if self.feedback else None
        except json.JSONDecodeError:
            feedback = None
        return Task(
            id=self.id, session_id=self.session_id, pipeline_id=self.pipeline_id,
            agent_type=self.agent_type, status=self.status,
            invoke_message=self.invoke_message, dependencies=deps,
            feedback=feedback, error=self.error,
            created_at=self.created_at, updated_at=self.updated_at,
            started_at=self.started_at, finished_at=self.finished_at,
            progress_total=self.progress_total,
        )

    @classmethod
    def from_domain(cls, task: Task) -> "TaskRow":
        return cls(
            id=task.id, session_id=task.session_id, pipeline_id=task.pipeline_id,
            agent_type=task.agent_type, status=task.status,
            invoke_message=task.invoke_message,
            dependencies=json.dumps(task.dependencies, ensure_ascii=False),
            feedback=json.dumps(task.feedback, ensure_ascii=False) if task.feedback is not None else None,
            error=task.error, created_at=task.created_at, updated_at=task.updated_at,
            started_at=task.started_at, finished_at=task.finished_at,
            progress_total=task.progress_total,
        )


_COLS = ", ".join(TaskRow.model_fields)
_PH = ", ".join(f":{k}" for k in TaskRow.model_fields)


class TaskRepository:
    def __init__(self, conn: ConnectionFactory):
        self._conn = conn
        self._conn.ensure_schema(_DDL)
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """幂等加列与迁列，建表语句不覆盖旧表。"""
        cols = {
            row["name"]
            for row in self._conn.get().execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "started_at" not in cols:
            self._conn.get().execute("ALTER TABLE tasks ADD COLUMN started_at REAL")
        if "finished_at" not in cols:
            self._conn.get().execute("ALTER TABLE tasks ADD COLUMN finished_at REAL")
        if "progress_total" not in cols:
            if "metadata" in cols:
                # 旧 metadata 列存 JSON，新建整型列拷值再丢弃旧列，避免类型亲和问题
                self._conn.get().execute(
                    "ALTER TABLE tasks ADD COLUMN progress_total INTEGER"
                )
                self._conn.get().execute(
                    "UPDATE tasks SET progress_total = json_extract(metadata, '$.progress_total') "
                    "WHERE metadata IS NOT NULL"
                )
                self._conn.get().execute("ALTER TABLE tasks DROP COLUMN metadata")
            else:
                self._conn.get().execute(
                    "ALTER TABLE tasks ADD COLUMN progress_total INTEGER"
                )

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

    def cas_update(
        self, task_id: str, from_status: str, to_status: str, **fields
    ) -> bool:
        """原子翻转：据原状态匹配更新，看影响行数。附加字段须在白名单内。"""
        bad = set(fields) - _CAS_FIELDS
        if bad:
            raise ValueError(f"cas_update 不允许字段: {bad}")
        sets = ["status=?", "updated_at=?"]
        params: list[object] = [to_status, fields.get("updated_at", time.time())]
        # JSON 列
        if "error" in fields:
            sets.append("error=?"); params.append(fields["error"])
        if "feedback" in fields:
            val = fields["feedback"]
            sets.append("feedback=?")
            params.append(json.dumps(val, ensure_ascii=False) if val is not None else None)
        # 浮点列
        for f in ("started_at", "finished_at"):
            if f in fields:
                sets.append(f"{f}=?"); params.append(fields[f])
        params.extend([task_id, from_status])
        cur = self._conn.get().execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id=? AND status=?", params
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
        if not statuses:
            return 0
        placeholders = ",".join("?" * len(statuses))
        now = time.time()
        with self._conn.transaction():
            cur = self._conn.get().execute(
                f"UPDATE tasks SET status='cancelled', updated_at=?, finished_at=? "
                f"WHERE pipeline_id=? AND status IN ({placeholders})",
                (now, now, pipeline_id, *statuses),
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
        if not statuses:
            return []
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
        if not statuses:
            return 0
        placeholders = ",".join("?" * len(statuses))
        row = self._conn.get().execute(
            f"SELECT COUNT(*) FROM tasks WHERE session_id=? AND status IN ({placeholders})",
            (session_id, *statuses),
        ).fetchone()
        return int(row[0]) if row else 0
