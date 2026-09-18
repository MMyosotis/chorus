"""已交付成品的跨仓储查询编排。"""
from __future__ import annotations

from typing import cast

from chorus.domain.task import (
    DeliveredProduct,
    PostCard,
    ProductCandidate,
    TaskStatus,
    list_products as build_product_list,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository


def load_delivered_products(
    task_repo: TaskRepository,
    artifacts_repo: TaskArtifactsRepository,
    session_id: str,
) -> list[DeliveredProduct]:
    """跨任务与产物仓储读取已交付成品。"""
    finished = task_repo.find_by_session_statuses(session_id, [TaskStatus.FINISHED])
    finalizers = [task for task in finished if task.agent_type == "finalize"]
    artifacts_by_task = artifacts_repo.load_many([task.id for task in finalizers])
    candidates = [
        ProductCandidate(
            task=task,
            card=cast(PostCard, artifacts_by_task[task.id].artifacts),
        )
        for task in finalizers
    ]
    return build_product_list(candidates)
