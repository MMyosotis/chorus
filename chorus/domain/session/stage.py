"""从门禁和任务状态派生会话阶段文案。"""

from __future__ import annotations

from typing import Optional

from chorus.domain.intent import IntentConfirmation
from chorus.domain.option import OptionPrompt
from chorus.domain.task.graph import TaskNodeView
from chorus.domain.task.models import AgentType, TaskStatus
from chorus.domain.task.profiles import AGENT_PROFILES

_TASK_STATE_LABELS: dict[TaskStatus, str] = {
    TaskStatus.RUNNING: "执行中",
    TaskStatus.AWAITING_CONFIRM: "等待确认",
    TaskStatus.FAILED: "需要处理",
}


def derive_stage(
    tasks: list[TaskNodeView],
    open_confirmation: Optional[IntentConfirmation],
    open_prompt: Optional[OptionPrompt],
) -> str:
    """从任务图快照与开放门禁派生会话阶段文案，门禁优先。"""
    return (
        _open_gate_stage(open_confirmation, open_prompt)
        or _active_task_stage(tasks)
        or ("已完成" if _has_finished_product(tasks) else None)
        or "自由对话"
    )


def _open_gate_stage(
    open_confirmation: Optional[IntentConfirmation],
    open_prompt: Optional[OptionPrompt],
) -> Optional[str]:
    if open_prompt is not None:
        return "等待选择"
    if open_confirmation is not None:
        return "等待确认"
    return None


def _active_task_stage(tasks: list[TaskNodeView]) -> Optional[str]:
    active = [task for task in tasks if task.is_stage_active()]
    if not active:
        return None
    task = min(active, key=lambda task_node: task_node.stage_sort_key())
    profile = AGENT_PROFILES[task.agent_type]
    return f"{profile.display_name} · {_TASK_STATE_LABELS[task.status]}"


def _has_finished_product(tasks: list[TaskNodeView]) -> bool:
    return any(
        task.status == TaskStatus.FINISHED and task.agent_type == AgentType.FINALIZE
        for task in tasks
    )
