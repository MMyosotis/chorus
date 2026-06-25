# kitty/domain/task/pipeline.py
"""任务图 pipeline 纯函数：steps 校验 / 整图展开 / 调用消息渲染 / 产物解析。

纯领域逻辑，不碰 DB、不 import repos/services/hooks/tools/agents。
- validate_steps：防模型编排漂移（杜撰角色/前向依赖/成环/漏 finalize），迭代拓扑判环非递归。
- expand_pipeline：按模型 steps 一次性成型整图（Task 列表，pending，deps 索引→task_id）。
- render_invoke_message：拼首轮 user 消息（stored invoke_message + deps 产物 + 重跑注入）。
- parse_sections / parse_output：分隔符切段 + JSON 段解析 + schema 校验。
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import ValidationError as PydValidationError

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.models import CreationIntent, StepSpec, Task, TaskStatus
from chorus.domain.task.post import PostCard, PostImage, PostSection
from chorus.domain.task.profiles import AGENT_PROFILES

_MAX_STEPS = 20


def validate_steps(steps: list[StepSpec]) -> None:
    """校验模型自主编排的 steps。非法抛 ValidationError 带 correction。

    - agent_type 必在 AGENT_PROFILES；deps 只引前置索引；无自指。
    - 至少 1 步；末步必为 finalize。
    - 迭代入度消解判环（非递归，嵌套<=3）。
    """
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
        for d in s.deps:
            if d == i:
                raise ValidationError(f"步骤{i}自指依赖", f"步骤{i}的 deps 不能引用自身")
            if d >= i or d < 0:
                raise ValidationError(
                    f"步骤{i}前向依赖: {d}",
                    f"步骤{i}的 deps 只能引用前置步骤索引(0..{i-1})",
                )
    if steps[-1].agent_type != "finalize":
        raise ValidationError("末步非 finalize", "最后一个步骤必须是 finalize，它是唯一成品出口")
    _check_acyclic(steps)


def _check_acyclic(steps: list[StepSpec]) -> None:
    """迭代入度消解判环（Kahn），剩余非空即有环。非递归。"""
    n = len(steps)
    indeg = [0] * n
    adj: list[list[int]] = [[] for _ in range(n)]
    for i, s in enumerate(steps):
        for d in s.deps:
            adj[d].append(i)
            indeg[i] += 1
    queue = [i for i in range(n) if indeg[i] == 0]
    visited = 0
    while queue:
        cur = queue.pop()
        visited += 1
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if visited != n:
        raise ValidationError("steps 存在依赖环", "步骤之间存在循环依赖，请检查 deps")


def expand_pipeline(intent: CreationIntent, steps: list[StepSpec]) -> list[Task]:
    """按 steps 一次性成型整图：每步生成 task_id，deps 索引解析为 task_id，
    invoke_message = intent 骨架 + 本步 focus。返回待落库 Task 列表（全 pending）。
    不落库（纯函数）。调用前应先 validate_steps。
    """
    pipeline_id = uuid.uuid4().hex
    ids = [uuid.uuid4().hex for _ in steps]
    now = 0.0  # 落库时由 service 用 clock 覆盖 created_at/updated_at
    tasks: list[Task] = []
    for i, s in enumerate(steps):
        deps_ids = [ids[d] for d in s.deps]
        invoke = _render_skeleton(intent, s)
        tasks.append(Task(
            id=ids[i], session_id="", pipeline_id=pipeline_id,
            agent_type=s.agent_type, seq=i + 1, status=TaskStatus.PENDING.value,
            invoke_message=invoke, dependencies=deps_ids,
            created_at=now, updated_at=now,
        ))
    return tasks


def _render_skeleton(intent: CreationIntent, step: StepSpec) -> str:
    """建图时渲染的 invoke_message 骨架：intent 摘要 + 本步 focus。"""
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
    """拼首轮 user 消息：stored invoke_message + deps 产物格式化 +（重跑）self_prior+feedback。

    deps_outputs: {task_id: 该 dep 的 step_output}。
    self_prior: 本 task 上轮产物（retry 重跑时非空），指示定向改进。
    feedback: 用户复核反馈（retry 时注入）。
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
    """按 <<<TAG:fmt>>>...<<<TAG_END>>> 切段，返回 {TAG: 原始文本}。

    容忍段外杂文（模型可能在段间加引导语），只取标签段。重复标签后写覆盖前写。
    """
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


def parse_output(content: str, agent_type: str) -> tuple[Any, dict]:
    """切段→按 fmt 解析→按 artifacts_schema 校验→返回 (artifacts, narrative)。

    失败抛 ValidationError 带 correction（缺段/字段错精确定位）。
    artifacts 校验：idea/script/image 校验形状字段存在；finalize 校验为整棵 PostCard。
    """
    profile = AGENT_PROFILES[agent_type]
    sections = parse_sections(content)
    if "artifacts" not in sections:
        raise ValidationError("缺 ARTIFACTS 段", f"请在 <<<ARTIFACTS:json>>>...<<<ARTIFACTS_END>>> 段内输出产物")
    if "narrative" not in sections:
        raise ValidationError("缺 NARRATIVE 段", f"请在 <<<NARRATIVE:json>>>...<<<NARRATIVE_END>>> 段内输出角色话术")
    artifacts = _parse_json(sections["artifacts"], "ARTIFACTS")
    narrative = _parse_json(sections["narrative"], "NARRATIVE")
    _validate_artifacts(artifacts, profile.artifacts_schema)
    _validate_narrative(narrative)
    return artifacts, narrative


def _parse_json(raw: str, tag: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"{tag} 段 JSON 解析失败: {e}", f"请把 {tag} 段内容写成合法 JSON") from e


def _validate_artifacts(artifacts: Any, schema: str) -> None:
    if not isinstance(artifacts, dict):
        raise ValidationError("artifacts 非对象", "ARTIFACTS 段须为 JSON 对象")
    if schema == "idea":
        if "candidates" not in artifacts:
            raise ValidationError("idea 缺 candidates", "ARTIFACTS 须含 candidates 数组")
    elif schema == "script":
        if "blocks" not in artifacts:
            raise ValidationError("script 缺 blocks", "ARTIFACTS 须含 blocks 数组")
    elif schema == "image":
        if "images" not in artifacts:
            raise ValidationError("image 缺 images", "ARTIFACTS 须含 images 数组")
    elif schema == "postcard":
        # finalize：校验为整棵 PostCard（Pydantic 强校验）
        try:
            PostCard(**artifacts)
        except PydValidationError as e:
            raise ValidationError(f"PostCard 校验失败: {e}", "finalize 产物须符合 PostCard 结构：title/sections[...] 等") from e


def _validate_narrative(narrative: Any) -> None:
    if not isinstance(narrative, dict):
        raise ValidationError("narrative 非对象", "NARRATIVE 段须为 JSON 对象")
    for key in ("busy_lines", "awaiting_line", "done_line"):
        if key not in narrative:
            raise ValidationError(f"narrative 缺 {key}", f"NARRATIVE 须含 {key}")
