"""任务产物表的唯一 SQL 入口：存产物 JSON，读写都经转换函数在裸数据和领域对象间互转。

每行自带角色，读回时按角色还原成对应的产物对象。
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from chorus.domain.task import TaskArtifacts
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.models import TaskArtifactsRecord


def _to_domain(r: TaskArtifactsRecord) -> TaskArtifacts:
    """按本行角色类型用注册表里的模型把 JSON 还原成强类型产物。"""
    artifacts = AGENT_PROFILES[r.agent_type].build_artifacts(r.artifacts)
    return TaskArtifacts(task_id=r.task_id, artifacts=artifacts)


def _from_domain(
    task_id: str, agent_type: str, artifacts: Any,
) -> TaskArtifactsRecord:
    return TaskArtifactsRecord(
        task_id=task_id, agent_type=agent_type,
        artifacts=dataclasses.asdict(artifacts),
    )


class TaskArtifactsRepository(BaseRepository):
    @write
    def upsert(
        self, db, task_id: str, agent_type: str, artifacts: Any,
    ) -> None:
        r = _from_domain(task_id, agent_type, artifacts)
        db.execute(
            insert(TaskArtifactsRecord)
            .values(task_id=r.task_id, agent_type=r.agent_type, artifacts=r.artifacts)
            .on_conflict_do_update(
                index_elements=["task_id"],
                set_={"agent_type": r.agent_type, "artifacts": r.artifacts},
            )
        )

    @read
    def load(self, db, task_id: str) -> Optional[TaskArtifacts]:
        r = db.get(TaskArtifactsRecord, task_id)
        return _to_domain(r) if r else None

    @read
    def load_many(self, db, task_ids: list[str]) -> dict[str, TaskArtifacts]:
        if not task_ids:
            return {}
        rs = db.scalars(
            select(TaskArtifactsRecord).where(TaskArtifactsRecord.task_id.in_(task_ids))
        ).all()
        return {r.task_id: _to_domain(r) for r in rs}
