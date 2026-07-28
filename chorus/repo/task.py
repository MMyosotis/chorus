"""任务表的唯一 SQL 入口。

只存调度、身份与状态机；任务内容见专门的内容表。状态集合由编排层传入，不硬编码。
"""
from __future__ import annotations

import time
from typing import Iterable, Optional

from sqlalchemy import func, select, update

from chorus.domain.log import get_logger
from chorus.domain.task import Task
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.mapping import shared_fields
from chorus.repo.models import TaskRecord

_logger = get_logger("repo.task")


def _to_domain(r: TaskRecord) -> Task:
    return Task(
        **shared_fields(r, Task, exclude={"dependencies"}),
        dependencies=list(r.dependencies or []),
    )


def _load_deps(db, task: Task) -> list[Task]:
    """按任务依赖标识加载依赖任务，跳过空标识与缺失行。"""
    deps: list[Task] = []
    for dep_id in task.dependencies:
        if not dep_id:
            continue
        dep = db.get(TaskRecord, dep_id)
        if dep is not None:
            deps.append(_to_domain(dep))
    return deps


def _from_domain(t: Task) -> TaskRecord:
    return TaskRecord(
        **shared_fields(t, TaskRecord, exclude={"dependencies"}),
        dependencies=list(t.dependencies),
    )


class TaskRepository(BaseRepository):
    @write
    def insert(self, db, task: Task) -> None:
        db.add(_from_domain(task))

    @read
    def get(self, db, task_id: str) -> Optional[Task]:
        r = db.get(TaskRecord, task_id)
        return _to_domain(r) if r else None

    @write
    def transition(self, db, task_id: str, to_status: str) -> bool:
        """状态翻转：直接设目标状态，更新时间自动刷新。返回是否命中行。"""
        result = db.execute(
            update(TaskRecord).where(TaskRecord.id == task_id)
            .values(status=to_status, updated_at=time.time())
        )
        hit = result.rowcount > 0
        _logger.info("transition", extra={"task_id": task_id, "to": to_status, "hit": hit})
        return hit

    @write
    def claim(self, db, task_id: str, now: float) -> bool:
        """scheduler 派发占槽：设为运行中并写归属与更新时间。"""
        result = db.execute(
            update(TaskRecord).where(TaskRecord.id == task_id)
            .values(status="running", owner_id=now, updated_at=now)
        )
        hit = result.rowcount > 0
        _logger.info("claim", extra={"task_id": task_id, "hit": hit})
        return hit

    @write
    def touch_updated_at(self, db, task_id: str) -> None:
        """心跳：直接更新时间，不走翻转不校验状态，防僵死误杀。"""
        db.execute(
            update(TaskRecord).where(TaskRecord.id == task_id).values(updated_at=time.time())
        )

    @write
    def cancel_pipeline(self, db, pipeline_id: str, statuses: Iterable[str]) -> int:
        """批量取消非终态任务，返回受影响行数。状态集合由编排层传入。"""
        statuses = list(statuses)
        now = time.time()
        result = db.execute(
            update(TaskRecord)
            .where(
                TaskRecord.pipeline_id == pipeline_id,
                TaskRecord.status.in_(statuses),
            )
            .values(status="cancelled", updated_at=now)
        )
        return result.rowcount

    @read
    def find_pending_with_deps(self, db) -> list[tuple[Task, list[Task]]]:
        """返回所有待执行任务及其依赖，调度判定交领域。"""
        pending = db.scalars(select(TaskRecord).where(TaskRecord.status == "pending")).all()
        result: list[tuple[Task, list[Task]]] = []
        for r in pending:
            task = _to_domain(r)
            result.append((task, _load_deps(db, task)))
        return result

    @read
    def find_running_before(self, db, cutoff_ts: float) -> list[Task]:
        rs = db.scalars(
            select(TaskRecord).where(
                TaskRecord.status == "running", TaskRecord.updated_at < cutoff_ts
            )
        ).all()
        return [_to_domain(r) for r in rs]

    @read
    def find_by_session_statuses(
        self, db, session_id: str, statuses: Iterable[str]
    ) -> list[Task]:
        statuses = list(statuses)
        rs = db.scalars(
            select(TaskRecord)
            .where(
                TaskRecord.session_id == session_id,
                TaskRecord.status.in_(statuses),
            )
            .order_by(TaskRecord.created_at, TaskRecord.id)
        ).all()
        return [_to_domain(r) for r in rs]

    @read
    def find_by_pipeline(self, db, pipeline_id: str) -> list[Task]:
        """返回流水线全部任务按创建升序，展示用拓扑序由编排层排。"""
        rs = db.scalars(
            select(TaskRecord).where(TaskRecord.pipeline_id == pipeline_id)
            .order_by(TaskRecord.created_at, TaskRecord.id)
        ).all()
        return [_to_domain(r) for r in rs]

    @read
    def count_by_session_statuses(
        self, db, session_id: str, statuses: Iterable[str]
    ) -> int:
        statuses = list(statuses)
        n = db.scalar(
            select(func.count(TaskRecord.id))
            .where(
                TaskRecord.session_id == session_id,
                TaskRecord.status.in_(statuses),
            )
        )
        return int(n or 0)
