"""任务图纯函数：步骤校验、整图展开、调用消息渲染、产物解析。

纯领域逻辑，不碰数据库。
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import ValidationError as PydValidationError

from chorus.domain.task import StepSpec, CreationIntent, Task, TaskContent
from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import CreationIntent, Narrative, StepSpec, Task, TaskContent, TaskStatus
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile

_MAX_STEPS = 20


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


def validate_one_step(index: int, step: StepSpec):
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

    bad = next((d for d in step.deps if not (0 <= d < index)), None)
    if bad is not None:
        raise ValidationError(
            f"步骤{index}依赖非前置步骤: {bad}",
            f"步骤{index}的 deps 只能引用前置步骤索引(0..{index - 1})",
        )


def expand_pipeline(
    intent: CreationIntent, steps: list[StepSpec], session_id: str, now: float,
) -> list[tuple[Task, TaskContent]]:
    """生成整图（调度行 + 内容行），初始全待执行，可直接落库。调用前应先校验。"""
    pipeline_id = uuid.uuid4().hex
    ids = [uuid.uuid4().hex for _ in steps]
    pairs: list[tuple[Task, TaskContent]] = []
    for index, step in enumerate(steps):
        appen_one_task(ids, index, intent, now, pairs, pipeline_id, session_id, step)
    return pairs


def appen_one_task(
    ids: list[str], index: int, intent: CreationIntent, now: float,
    pairs: list[tuple[Task, TaskContent]], pipeline_id: str, session_id: str, step: StepSpec
):
    deps_ids = [ids[dep] for dep in step.deps]
    invoke = _render_skeleton(intent, step)
    progress_total = intent.image_count if step.agent_type == "image" else None
    task_id = ids[index]

    task = Task(
        id=task_id, session_id=session_id, pipeline_id=pipeline_id,
        agent_type=step.agent_type, status=TaskStatus.PENDING.value,
        dependencies=deps_ids, created_at=now, updated_at=now,
    )
    task_content = TaskContent(
        task_id=task_id, invoke_message=invoke, progress_total=progress_total
    )
    pairs.append((task, task_content))


def _render_skeleton(intent: CreationIntent, step: StepSpec) -> str:
    lines = [
        f"创作主题：{intent.topic}",
        f"风格倾向：{intent.style or '（未指定）'}",
        f"配图数量：{intent.image_count}",
    ]
    if intent.extra:
        lines.append(f"其它要求：{json.dumps(intent.extra, ensure_ascii=False)}")
    lines.append(f"本步职责：{step.focus}")
    lines.append(f"角色：{AGENT_PROFILES[step.agent_type].display_name}")
    return "\n".join(lines)


def render_invoke_message(
    invoke_message: str, deps_outputs: dict[str, Any], self_prior: Optional[Any], feedback: Optional[dict],
) -> str:
    """拼首轮调用消息：基础骨架，按需附前置产物、上轮产物、用户反馈。"""
    parts = [invoke_message]
    if deps_outputs:
        parts.append("前置步骤产物：")
        for dep_id, out in deps_outputs.items():
            parts.append(f"--- {dep_id} ---\n{json.dumps(out, ensure_ascii=False, indent=2)}")

    if self_prior is not None:
        parts.append("你上一轮的产物（据此定向改进，不要简单重复）：")
        parts.append(json.dumps(self_prior, ensure_ascii=False, indent=2))

    if feedback:
        parts.append("用户反馈（请据此改进）：")
        parts.append(json.dumps(feedback, ensure_ascii=False, indent=2))

    return "\n\n".join(parts)


_SECTION_OPEN = "<<<"
_SECTION_CLOSE = ">>>"


def parse_sections(content: str) -> dict[str, str]:
    """按分隔符切段，容忍段外杂文，重复标签后者覆盖。

    段格式：``<<<TAG:fmt>>>正文<<<TAG_END>>>``，``:fmt`` 可省。
    """
    sections: dict[str, str] = {}
    pos = 0
    while pos < len(content):
        open_at = content.find(_SECTION_OPEN, pos)
        if open_at == -1:
            break
        header_close = content.find(_SECTION_CLOSE, open_at)
        if header_close == -1:
            break
        header = content[open_at + len(_SECTION_OPEN):header_close]
        tag = header.split(":", 1)[0]

        end_marker = f"{_SECTION_OPEN}{tag}_END{_SECTION_CLOSE}"
        body_start = header_close + len(_SECTION_CLOSE)
        body_end = content.find(end_marker, body_start)
        if body_end == -1:
            break

        sections[tag.strip().lower()] = content[body_start:body_end].strip()
        pos = body_end + len(end_marker)
    return sections


def parse_output(content: str, agent_type: str) -> tuple[Any, Narrative]:
    """切段、解析、按角色模型校验。失败抛异常并精确定位缺段或字段错。"""
    profile = AGENT_PROFILES[agent_type]
    sections = parse_sections(content)
    if "artifacts" not in sections:
        raise ValidationError("缺 ARTIFACTS 段", f"请在 <<<ARTIFACTS:json>>>...<<<ARTIFACTS_END>>> 段内输出产物")
    if "narrative" not in sections:
        raise ValidationError("缺 NARRATIVE 段", f"请在 <<<NARRATIVE:json>>>...<<<NARRATIVE_END>>> 段内输出角色话术")
    artifacts = _parse_json(sections["artifacts"], "ARTIFACTS")
    artifacts = _validate_artifacts(artifacts, profile)
    narrative = _parse_json(sections["narrative"], "NARRATIVE")
    narrative = _validate_narrative(narrative)
    return artifacts, narrative


def _validate_narrative(data: Any) -> Narrative:
    """构造即校验，失败转异常并附修正提示。"""
    try:
        return Narrative(**data)
    except PydValidationError as e:
        raise ValidationError(
            f"NARRATIVE 校验失败: {e}",
            "NARRATIVE 须含 awaiting_line/done_line(字符串)",
        ) from e


def _parse_json(raw: str, tag: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"{tag} 段 JSON 解析失败: {e}", f"请把 {tag} 段内容写成合法 JSON") from e


def _validate_artifacts(artifacts: Any, profile: AgentProfile) -> Any:
    """用角色对应的模型构造即校验，新增角色无需改本函数。"""
    try:
        return profile.artifacts_model(**artifacts)
    except PydValidationError as e:
        raise ValidationError(
            f"ARTIFACTS 校验失败: {e}",
            f"{profile.display_name}产物须符合 {profile.artifacts_model.__name__} 结构",
        ) from e
