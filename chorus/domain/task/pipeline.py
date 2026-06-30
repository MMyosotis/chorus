# kitty/domain/task/pipeline.py
"""任务图 pipeline 纯函数：steps 校验 / 整图展开 / 调用消息渲染 / 产物解析。

纯领域逻辑，不碰 DB、不 import repos/services/hooks/tools/agents。
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import ValidationError as PydValidationError

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import CreationIntent, Narrative, StepSpec, Task, TaskStatus
from chorus.domain.task.profiles import AGENT_PROFILES, AgentProfile

_MAX_STEPS = 20


def validate_steps(steps: list[StepSpec]) -> None:
    """校验模型自主编排的 steps。非法抛 ValidationError 带 correction。"""
    if not steps:
        raise ValidationError("steps 为空", "请至少编排一个创作步骤，末步须为 finalize 汇总")
    if len(steps) > _MAX_STEPS:
        raise ValidationError(f"steps 过多({len(steps)})", f"步骤数不超过 {_MAX_STEPS}")

    for i, s in enumerate(steps):
        if s.agent_type not in AGENT_PROFILES:
            raise ValidationError(
                f"步骤{i}角色非法: {s.agent_type}",
                f"步骤{i}的 agent_type 必须是 idea/script/image/finalize 之一",
            )
        if i > 0 and not s.deps:
            raise ValidationError(
                f"步骤{i}无依赖",
                f"步骤{i}必须依赖至少一个前置步骤（仅首步可无依赖）",
            )
        bad = next((d for d in s.deps if not (0 <= d < i)), None)
        if bad is not None:
            raise ValidationError(
                f"步骤{i}依赖非前置步骤: {bad}",
                f"步骤{i}的 deps 只能引用前置步骤索引(0..{i-1})",
            )

    if steps[-1].agent_type != "finalize":
        raise ValidationError("末步非 finalize", "最后一个步骤必须是 finalize，它是唯一成品出口")


def expand_pipeline(
    intent: CreationIntent, steps: list[StepSpec], session_id: str, now: float,
) -> list[Task]:
    """按 steps 一次性成型整图（全 pending，可直接落库）。

    纯函数：session_id/now 由编排层传入。调用前应先 validate_steps。
    """
    pipeline_id = uuid.uuid4().hex
    ids = [uuid.uuid4().hex for _ in steps]
    tasks: list[Task] = []
    for i, s in enumerate(steps):
        deps_ids = [ids[dep] for dep in s.deps]
        invoke = _render_skeleton(intent, s)
        metadata = (
            {"goal": f"生成 {intent.image_count} 张配图",
             "progress_total": intent.image_count, "progress_unit": "张图"}
            if s.agent_type == "image" else None
        )
        tasks.append(Task(
            id=ids[i], session_id=session_id, pipeline_id=pipeline_id,
            agent_type=s.agent_type, seq=i + 1, status=TaskStatus.PENDING.value,
            invoke_message=invoke, dependencies=deps_ids,
            created_at=now, updated_at=now, metadata=metadata,
        ))
    return tasks


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
    task: Task,
    deps_outputs: dict[str, Any],
    self_prior: Optional[Any],
    feedback: Optional[dict],
) -> str:
    """拼首轮 user 消息：invoke_message + deps 产物 +（重跑）self_prior/feedback。

    - deps_outputs: {task_id: 该 dep 的 artifacts}
    - self_prior: 本 task 上轮产物（retry 时非空），指示定向改进
    - feedback: 用户复核反馈（retry 时注入）
    """
    parts = [task.invoke_message]
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


def parse_sections(content: str) -> dict[str, str]:
    """按 <<<TAG:fmt>>>...<<<TAG_END>>> 切段。容忍段外杂文，只取标签段；重复标签后写覆盖。"""
    result: dict[str, str] = {}
    i = 0
    n = len(content)
    while i < n:
        start = content.find("<<<", i)
        if start == -1:
            break
        header_end = content.find(">>>", start)
        if header_end == -1:
            break
        header = content[start + 3:header_end]  # e.g. "ARTIFACTS:json"
        if ":" in header:
            tag, _fmt = header.split(":", 1)
        else:
            tag = header
        close = f"<<<{tag}_END>>>"
        body_start = header_end + 3
        body_end = content.find(close, body_start)
        if body_end == -1:
            break
        result[tag.strip().lower()] = content[body_start:body_end].strip()
        i = body_end + len(close)
    return result


def parse_output(content: str, agent_type: str) -> tuple[Any, Narrative]:
    """切段→解析→按 profile 模型校验。失败抛 ValidationError 带 correction（缺段/字段错精确定位）。"""
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
    """构造即校验，失败转 ValidationError 带 correction。"""
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
    """用 profile.artifacts_model 构造即校验。不认识具体角色——新增 profile 零改动（开闭）。"""
    try:
        return profile.artifacts_model(**artifacts)
    except PydValidationError as e:
        raise ValidationError(
            f"ARTIFACTS 校验失败: {e}",
            f"{profile.display_name}产物须符合 {profile.artifacts_model.__name__} 结构",
        ) from e
