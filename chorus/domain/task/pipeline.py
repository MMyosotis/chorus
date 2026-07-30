"""任务图纯函数：步骤校验、整图展开、调用消息渲染规格，不碰数据库。"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from chorus.domain.intent import Intent
from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import Task, TaskContent, TaskStatus
from chorus.domain.task.profiles import AGENT_PROFILES

_MAX_STEPS = 20


@dataclass
class StepSpec:
    """建图前的单步规格，落库后依赖由索引解析为任务标识。"""

    agent_type: str
    deps: list[int]


@dataclass
class TaskPlan:
    """已确认意图及其执行步骤，可展开为待调度任务图。"""

    session_id: str
    intent: Intent
    steps: list[StepSpec]
    message_id: Optional[str] = None
    pipeline_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.steps:
            raise ValidationError("steps 为空", "请至少编排一个创作步骤，末步须为 finalize 汇总")
        if len(self.steps) > _MAX_STEPS:
            raise ValidationError(
                f"steps 过多({len(self.steps)})",
                f"步骤数不超过 {_MAX_STEPS}",
            )

        for index in range(len(self.steps)):
            self._validate_step(index)

        if self.steps[-1].agent_type != "finalize":
            raise ValidationError("末步非 finalize", "最后一个步骤必须是 finalize，它是唯一成品出口")

    def _validate_step(self, index: int) -> None:
        step = self.steps[index]
        if step.agent_type not in AGENT_PROFILES:
            raise ValidationError(
                f"步骤{index}角色非法: {step.agent_type}",
                f"步骤{index}的 agent_type 必须是 idea/script/image/finalize 之一",
            )

        if index > 0 and not step.deps:
            raise ValidationError(
                f"步骤{index}无依赖",
                f"步骤{index}必须依赖至少一个前置步骤（仅首步可无依赖）",
            )

        bad = next((dep for dep in step.deps if not (0 <= dep < index)), None)
        if bad is not None:
            raise ValidationError(
                f"步骤{index}依赖非前置步骤: {bad}",
                f"步骤{index}的 deps 只能引用前置步骤索引(0..{index - 1})",
            )

    def expand(self) -> list[tuple[Task, TaskContent]]:
        ids = [uuid.uuid4().hex for _ in self.steps]
        return [
            self._one_task(ids, index)
            for index in range(len(self.steps))
        ]

    def _one_task(self, ids: list[str], index: int) -> tuple[Task, TaskContent]:
        step = self.steps[index]
        task_id = ids[index]
        task = Task(
            id=task_id, session_id=self.session_id, message_id=self.message_id, pipeline_id=self.pipeline_id,
            agent_type=step.agent_type, status=TaskStatus.PENDING,
            dependencies=[ids[dep] for dep in step.deps],
            created_at=self.created_at, updated_at=self.created_at,
        )
        content = TaskContent(
            task_id=task_id,
            invoke_message=self._render_skeleton(step),
        )
        return task, content

    def _render_skeleton(self, step: StepSpec) -> str:
        """完整意图 JSON + 角色，不逐字段拆解。"""
        return "\n".join([
            "创作意图：",
            json.dumps(self.intent.model_dump(mode="json"), ensure_ascii=False, indent=2),
            f"角色：{AGENT_PROFILES[step.agent_type].display_name}",
        ])
