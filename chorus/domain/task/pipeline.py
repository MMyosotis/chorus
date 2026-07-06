"""任务图纯函数：步骤校验、整图展开、调用消息渲染规格，不碰数据库。"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import Task, TaskContent, TaskStatus
from chorus.domain.task.profiles import AGENT_PROFILES

_MAX_STEPS = 20


@dataclass
class CreationIntent:
    """从建图工具参数解析的创作意图。"""

    topic: str
    style: str = ""
    image_count: int = 3
    extra: dict = field(default_factory=dict)

    def expand_to_tasks(
        self, steps: list["StepSpec"], session_id: str, now: float,
    ) -> list[tuple[Task, TaskContent]]:
        """生成整图（调度行 + 内容行），初始全待执行，可直接落库。调用前应先校验。"""
        pipeline_id = uuid.uuid4().hex
        ids = [uuid.uuid4().hex for _ in steps]
        pairs: list[tuple[Task, TaskContent]] = []
        for index, step in enumerate(steps):
            pairs.append(self._one_task(ids, index, step, pipeline_id, session_id, now))
        return pairs

    def _one_task(
        self, ids: list[str], index: int, step: "StepSpec", pipeline_id: str, session_id: str, now: float,
    ) -> tuple[Task, TaskContent]:
        deps_ids = [ids[dep] for dep in step.deps]
        task_id = ids[index]
        task = Task(
            id=task_id, session_id=session_id, pipeline_id=pipeline_id,
            agent_type=step.agent_type, status=TaskStatus.PENDING,
            dependencies=deps_ids, created_at=now, updated_at=now,
        )
        content = TaskContent(
            task_id=task_id,
            invoke_message=self._render_skeleton(step),
            progress_total=self.image_count if step.agent_type == "image" else None,
        )
        return task, content

    def _render_skeleton(self, step: "StepSpec") -> str:
        lines = [
            f"创作主题：{self.topic}",
            f"风格倾向：{self.style or '（未指定）'}",
            f"配图数量：{self.image_count}",
        ]
        if self.extra:
            lines.append(f"其它要求：{json.dumps(self.extra, ensure_ascii=False)}")
        lines.append(f"本步职责：{step.focus}")
        lines.append(f"角色：{AGENT_PROFILES[step.agent_type].display_name}")
        return "\n".join(lines)


@dataclass
class StepSpec:
    """建图前的单步规格，落库后依赖由索引解析为任务标识。"""

    agent_type: str
    deps: list[int]
    focus: str


def validate_steps(steps: list[StepSpec]) -> None:
    """校验模型编排的步骤，非法抛异常并附修正提示。"""
    if not steps:
        raise ValidationError("steps 为空", "请至少编排一个创作步骤，末步须为 finalize 汇总")
    if len(steps) > _MAX_STEPS:
        raise ValidationError(f"steps 过多({len(steps)})", f"步骤数不超过 {_MAX_STEPS}")

    for index, step in enumerate(steps):
        validate_one_step(index, step)

    if steps[-1].agent_type != "finalize":
        raise ValidationError("末步非 finalize", "最后一个步骤必须是 finalize，它是唯一成品出口")


def validate_one_step(index: int, step: StepSpec) -> None:
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
