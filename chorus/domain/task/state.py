"""任务图状态机：转移规则表与基于集合的判定函数。

状态语义集中此处，终态冻结，失败不级联，后继待依赖全完成方可调度。"""
from __future__ import annotations

from dataclasses import dataclass

from chorus.domain.task.models import Task, TaskStatus

ACTIVE_STATUSES: frozenset[str] = frozenset({
    TaskStatus.PENDING,
    TaskStatus.RUNNING,
    TaskStatus.AWAITING_CONFIRM,
})
TERMINAL_STATUSES: frozenset[str] = frozenset({
    TaskStatus.FINISHED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
})
CANCELLABLE_STATUSES: frozenset[str] = frozenset({
    TaskStatus.PENDING,
    TaskStatus.AWAITING_CONFIRM,
})

LEGAL_TRANSITIONS: set[tuple[str, str]] = {
    (TaskStatus.PENDING, TaskStatus.RUNNING),
    (TaskStatus.RUNNING, TaskStatus.AWAITING_CONFIRM),
    (TaskStatus.RUNNING, TaskStatus.FINISHED),
    (TaskStatus.RUNNING, TaskStatus.FAILED),
    (TaskStatus.AWAITING_CONFIRM, TaskStatus.FINISHED),
    (TaskStatus.AWAITING_CONFIRM, TaskStatus.PENDING),
    (TaskStatus.AWAITING_CONFIRM, TaskStatus.CANCELLED),
    (TaskStatus.PENDING, TaskStatus.CANCELLED),
    (TaskStatus.FAILED, TaskStatus.PENDING),
}


def is_legal_transition(from_status: str, to_status: str) -> bool:
    """是否合法转移。终态不可再转移。"""
    return (from_status, to_status) in LEGAL_TRANSITIONS


def topological_order(tasks: list[Task]) -> list[Task]:
    """按依赖拓扑排序，同层按创建时间再标识兜底，把图拍平为展示序列。

    无环由入库前校验保证，本函数不重复检测。引用列表外依赖时该边忽略。
    """
    graph = _DegreeGraph(
        task_by_id={task.id: task for task in tasks},
        in_degree={task.id: 0 for task in tasks},
        dependents={task.id: [] for task in tasks},
    )

    for task in tasks:
        _link_task_dependencies(graph, task)

    ordered: list[Task] = []
    remaining = set(graph.in_degree)
    while remaining:
        ready = [task_id for task_id in remaining if graph.in_degree[task_id] == 0]
        ready.sort(key=lambda task_id: (graph.task_by_id[task_id].created_at, task_id))
        _drain_ready_layer(graph, ordered, ready, remaining)

    return ordered


@dataclass(frozen=True)
class _DegreeGraph:
    """拓扑排序用的图三件套：节点索引 + 入度表 + 反向邻接表。"""

    task_by_id: dict[str, Task]
    in_degree: dict[str, int]
    dependents: dict[str, list[str]]


def _drain_ready_layer(
    graph: _DegreeGraph, ordered: list[Task], ready: list[str], remaining: set[str]
) -> None:
    for task_id in ready:
        ordered.append(graph.task_by_id[task_id])
        remaining.discard(task_id)
        _decrement_in_degree(graph.dependents[task_id], graph.in_degree)


def _link_task_dependencies(graph: _DegreeGraph, task: Task) -> None:
    for dep_id in (dep for dep in task.dependencies if dep in graph.task_by_id):
        graph.in_degree[task.id] += 1
        graph.dependents[dep_id].append(task.id)


def _decrement_in_degree(targets: list[str], in_degree: dict[str, int]) -> None:
    """批量削减后继节点入度。"""
    for task_id in targets:
        in_degree[task_id] -= 1


def select_display_pipeline(
    active: list[Task], finished: list[Task]
) -> list[Task]:
    """展示用流水线：有进行中则返进行中，否则返已完成与失败（已取消不算）。"""
    if active:
        return active
    return [task for task in finished if task.status in (TaskStatus.FINISHED, TaskStatus.FAILED)]
