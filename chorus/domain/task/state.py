"""任务图状态机：转移规则表与基于集合的判定函数。

状态语义集中此处。终态冻结，失败不级联——后继待依赖全完成方可调度。
"""
from __future__ import annotations

from typing import Iterable

from chorus.domain.task.models import Task, TaskStatus

# 状态集合常量
ACTIVE_STATUSES: frozenset[str] = frozenset({
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
    TaskStatus.AWAITING_CONFIRM.value,
})
TERMINAL_STATUSES: frozenset[str] = frozenset({
    TaskStatus.FINISHED.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
})
# 可批量取消的集合，等于全部非终态
CANCELLABLE_STATUSES: frozenset[str] = frozenset({
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
    TaskStatus.AWAITING_CONFIRM.value,
})

# 合法转移规则表（亦作测试夹具）
LEGAL_TRANSITIONS: set[tuple[str, str]] = {
    (TaskStatus.PENDING.value, TaskStatus.RUNNING.value),            # scheduler CAS
    (TaskStatus.RUNNING.value, TaskStatus.AWAITING_CONFIRM.value),   # worker（需复核步）
    (TaskStatus.RUNNING.value, TaskStatus.FINISHED.value),           # worker（finalize 无需复核）
    (TaskStatus.RUNNING.value, TaskStatus.FAILED.value),             # worker except
    (TaskStatus.RUNNING.value, TaskStatus.CANCELLED.value),          # cancel_pipeline 批量翻转
    (TaskStatus.RUNNING.value, TaskStatus.PENDING.value),            # scheduler zombie 回收
    (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.FINISHED.value),  # confirm API CAS
    (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.PENDING.value),   # retry API CAS（带 feedback）
    (TaskStatus.AWAITING_CONFIRM.value, TaskStatus.CANCELLED.value), # cancel API CAS
    (TaskStatus.PENDING.value, TaskStatus.CANCELLED.value),          # cancel API CAS
    (TaskStatus.FAILED.value, TaskStatus.PENDING.value),             # retry API CAS（带 feedback）
}


def is_legal_transition(from_status: str, to_status: str) -> bool:
    """是否合法转移。终态不可再转移。"""
    return (from_status, to_status) in LEGAL_TRANSITIONS


def can_schedule(task: Task, deps: Iterable[Task]) -> bool:
    """可调度：待执行且所有依赖均已完成。失败的上游会阻塞后继。"""
    if task.status != TaskStatus.PENDING.value:
        return False
    return all(d.status == TaskStatus.FINISHED.value for d in deps)


def is_zombie(task: Task, now: float, timeout_s: int) -> bool:
    """是否僵死：运行中且心跳超时。"""
    if task.status != TaskStatus.RUNNING.value:
        return False
    return (now - task.updated_at) > timeout_s


def topological_order(tasks: list[Task]) -> list[Task]:
    """按依赖拓扑排序，同层按创建时间再标识兜底，把图拍平为展示序列。

    无环由入库前校验保证，本函数不重复检测。引用列表外依赖时该边忽略。
    """
    by_id = {t.id: t for t in tasks}
    indeg: dict[str, int] = {t.id: 0 for t in tasks}
    children: dict[str, list[str]] = {t.id: [] for t in tasks}
    for t in tasks:
        for dep_id in (d for d in t.dependencies if d in by_id):
            indeg[t.id] += 1
            children[dep_id].append(t.id)
    ordered: list[Task] = []
    remaining = set(indeg)
    while remaining:
        ready = sorted(
            (tid for tid in remaining if indeg[tid] == 0),
            key=lambda i: (by_id[i].created_at, i),
        )
        for tid in ready:
            ordered.append(by_id[tid])
            remaining.discard(tid)
            _decrement_indeg(children[tid], indeg)
    return ordered


def _decrement_indeg(targets: list[str], indeg: dict[str, int]) -> None:
    """批量削减后继节点入度。"""
    for tid in targets:
        indeg[tid] -= 1


def select_display_pipeline(
    active: list[Task], finished: list[Task]
) -> list[Task]:
    """展示用流水线：有进行中则返进行中，否则返已完成（已取消不算）。"""
    if active:
        return active
    finished_only = [t for t in finished if t.status == TaskStatus.FINISHED.value]
    return finished_only
