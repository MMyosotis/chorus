# kitty/repo/task.py
"""tasks 表的唯一 SQL 入口（哑查询，永不开事务，无业务规则）。

表结构见 spec 3.1。CAS 合法性分工：domain 出 LEGAL_TRANSITIONS 规则表；service 方法
结构性只做一条合法翻转；repo cas_update 仅原子原语（WHERE status=from 看 rowcount），
不管翻转合不合法。状态集合由 service 从 domain 传入（WHERE status IN ?），repo 不硬编码。
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

# cas_update 允许顺带更新的字段（白名单，防 SQL 注入与误写）
_CAS_FIELDS = {"error", "feedback", "updated_at", "started_at", "finished_at"}
# 注：progress_total 建图期 insert 一次性写入，不进 CAS（运行期不可变）


class TaskRow(BaseModel):
    """tasks 表持久化形状（1:1 贴列）。映射归框架，转换归 to_domain/from_domain。

    dependencies/feedback 是 JSON 列；agent_type/status 在领域即 str（存 enum 值），无转换。
    """

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
        """幂等加列/迁列（无迁移框架，CREATE TABLE IF NOT EXISTS 不覆盖已存在的旧表）。"""
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
                # 旧 metadata 列存 JSON {"progress_total":N}：新建 INTEGER 列拷值，再丢弃旧列
                #（rename 会保留 TEXT affinity 导致 int 被强转成文本，故走 add+drop）
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
        """原子原语：UPDATE ... WHERE id=? AND status=from_status，看 rowcount。
        **fields 仅允许 error/feedback/updated_at/started_at/finished_at。
        error/feedback 走 JSON；started_at/finished_at 是裸 float。
        """
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
        # 裸 float 列
        for f in ("started_at", "finished_at"):
            if f in fields:
                sets.append(f"{f}=?"); params.append(fields[f])
        params.extend([task_id, from_status])
        cur = self._conn.get().execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id=? AND status=?", params
        )
        return cur.rowcount > 0

    def touch_updated_at(self, task_id: str) -> None:
        """心跳：直接更新 updated_at（不走 CAS、不校验状态）。供 subagent 每轮防 zombie 误杀。"""
        self._conn.get().execute(
            "UPDATE tasks SET updated_at=? WHERE id=?", (time.time(), task_id)
        )

    def cancel_pipeline(self, pipeline_id: str, statuses: Iterable[str]) -> int:
        """事务内批量 CAS 非终态 task→cancelled。返受影响行数。

        状态集合由 service 从 domain CANCELLABLE_STATUSES 传入（repo 不硬编码业务规则）。
        """
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
        """返所有 pending task + 其 deps 行（哑查询，调度判定交 domain can_schedule）。"""
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
        """该 pipeline 全部 task（按 created_at 升序，含终态）。哑查询；展示用拓扑序由 service 排。"""
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
