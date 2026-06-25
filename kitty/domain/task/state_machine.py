# kitty/domain/task/state_machine.py
"""任务图状态机：转移规则表 + 基于集合运算的纯判定函数。

所有状态语义集中此处一处。加状态=枚举+规则表+决定集合归属；加转移=规则表+一处
service cas_update 调用；repo 零状态硬编码（哑 WHERE status IN ?, 集合由 service 传入）。
严格闸门不变式：无 finished→* 转移（finished 即冻结）。砍级联失败：上游 failed
不动后继，后继 pending 由 can_schedule 阻塞（deps 须全 finished）。
"""
from __future__ import annotations

from typing import Iterable

from kitty.domain.task.models import Task, TaskStatus

# —— 状态集合常量（frozenset[str]，用 TaskStatus.value）——
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
# cancel 端点可批量翻转的集合（= 全部非终态）
CANCELLABLE_STATUSES: frozenset[str] = frozenset({
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
    TaskStatus.AWAITING_CONFIRM.value,
})

# —— 合法转移规则表（唯一真相源 + 测试夹具）——
# (from_status, to_status): owner 注释（注释仅文档，不参与逻辑）
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
    """是否合法转移。严格闸门：无 finished→*（finished 不在 from 集）。"""
    return (from_status, to_status) in LEGAL_TRANSITIONS


def can_schedule(task: Task, deps: Iterable[Task]) -> bool:
    """task 可调度：pending 且所有 deps 均 finished。砍级联——failed 上游不满足，后继阻塞。"""
    if task.status != TaskStatus.PENDING.value:
        return False
    return all(d.status == TaskStatus.FINISHED.value for d in deps)


def is_zombie(task: Task, now: float, timeout_s: int) -> bool:
    """task 僵尸：running 且 (now - updated_at) > timeout_s。"""
    if task.status != TaskStatus.RUNNING.value:
        return False
    return (now - task.updated_at) > timeout_s


def select_display_pipeline(
    active: list[Task], finished: list[Task]
) -> list[Task]:
    """前端展示用 pipeline：active 非空返 active，否则返最近 finished（cancelled 不算）。

    get_graph 调用：active = 该 pipeline 仍含非终态 task 的列表；finished = 全终态的历史
    pipeline 列表。cancelled 的 pipeline 不作 finished 历史回看。
    """
    if active:
        return active
    finished_only = [t for t in finished if t.status == TaskStatus.FINISHED.value]
    return finished_only
