"""建图工具：解析、校验、整图成型与事务落库全在工具内收口。

对模型是普通工具，主流程只据挂起信号关流本轮。可预料失败返回传由模型自纠，
仅意外异常由派发层兜底。挂起收口的回执也在此拼装：由最近一张图的状态推导
成品直给或取消一句话。
"""
from __future__ import annotations

from typing import Optional, cast

from pydantic import ValidationError as PydanticValidationError

from chorus.domain.intent import Intent
from chorus.domain.prompt import SkeletonInputs, build_task_content
from chorus.domain.task import (
    CANCELLED_PIPELINE_RECEIPT,
    AgentType,
    PostCard,
    StepSpec,
    TaskArtifacts,
    TaskPlan,
    TaskStatus,
    ValidationError,
    format_product_list,
    render_delivery_receipt,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.task import TaskService
from chorus.tools.framework import Reply, Suspend, Tool, ToolContext, ToolRunResult


class CreatePlanTool(Tool):
    name = "create_plan"
    description = (
        "当用户要创作图文博文时调用，按用户实际自主编排创作步骤；"
        "普通对话直接文本回复不调用本工具。修订已交付成品时，"
        "把此前收口回执给出的成品标识填作底稿标识。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "thought": {"type": "string", "description": "内部思考，不展示给用户"},
            "intent": {
                "type": "object",
                "properties": Intent.tool_schema_properties(
                    "topic", "platform", "format", "style", "image_count", "extra",
                ),
                "required": ["topic"],
            },
            "base_product_id": {
                "type": "string",
                "description": "底稿标识：修订所基于的已交付成品（排版任务 id），"
                "取此前收口回执给出的成品标识；全新创作不填",
            },
            "steps": {
                "type": "array",
                "description": "创作步骤序列；末步须为 finalize；deps 引用 steps 内前置索引",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_type": {
                            "type": "string",
                            "enum": ["idea", "script", "image", "finalize"],
                        },
                        "deps": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "前置步骤索引(0-based)",
                        },
                        "note": {
                            "type": "string",
                            "description": "本步交待：给该步骤的捎话，修订时说清改哪留哪，可不填",
                        },
                    },
                    "required": ["agent_type", "deps"],
                },
            },
        },
        "required": ["thought", "intent", "steps"],
    }
    running_label = "编排创作任务"

    def __init__(
        self,
        task_repo: TaskRepository,
        task_service: TaskService,
        content_repo: TaskContentRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        intent_state: IntentStateService,
    ):
        self._task_repo = task_repo
        self._task_service = task_service
        self._content_repo = content_repo
        self._artifacts_repo = task_artifacts_repo
        self._intent_state = intent_state

    def display(self, arguments: dict) -> str:
        topic = (arguments.get("intent", {}) or {}).get("topic", "")
        return f"创作：{topic or '(未指定主题)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        session_id = cast(str, ctx.session_id)
        blocked = self._intent_gate(session_id)
        if blocked:
            return ToolRunResult(blocked, is_error=True)
        try:
            base_product_id = arguments.get("base_product_id")
            base_card = self._load_base_card(session_id, cast(str, base_product_id)) if base_product_id else None
            pairs = self._build_pairs(arguments, session_id, ctx.message_id, base_card)
        except (KeyError, TypeError, ValueError, PydanticValidationError) as e:
            return ToolRunResult(Reply(f"create_plan 参数缺失或格式错: {e}"), is_error=True)
        except ValidationError as e:
            return ToolRunResult(Reply(e.correction), is_error=True)
        self._persist(pairs)
        return ToolRunResult(self._finalize(pairs))

    def _intent_gate(self, session_id: str):
        """意图未确认则返阻塞回执，已确认返 None。"""
        if self._intent_state.is_confirmed(session_id):
            return None
        state = self._intent_state.get(session_id)
        return Reply(
            "create_plan blocked: 当前意图尚未由用户确认。"
            f"intent_status={state.intent_status}。请先继续澄清意图，"
            "或在 ready_to_confirm 后等待用户确认。"
        )

    def _load_base_card(self, session_id: str, base_product_id: str) -> PostCard:
        """按底稿标识直查校验并冻结成品卡，无效抛校验错打回。"""
        task = self._task_repo.get(base_product_id)
        if task is not None and task.session_id == session_id and task.is_delivered():
            loaded = cast(TaskArtifacts, self._artifacts_repo.load(base_product_id))
            return cast(PostCard, loaded.artifacts)

        products = self._task_service.list_products(session_id)
        raise ValidationError(
            f"底稿标识无效: {base_product_id}",
            "底稿标识须是本会话已交付成品的排版任务 id。\n"
            f"当前可用的成品：\n{format_product_list(products)}",
        )

    def _build_pairs(self, arguments: dict, session_id: str, message_id: Optional[str], base_card: Optional[PostCard]):
        """解析 steps、整份 intent 透传（不逐字段拆解）、校验，展开并渲染骨架内容行。"""
        intent = Intent.model_validate(arguments["intent"])
        steps = [
            StepSpec(agent_type=AgentType(step["agent_type"]), deps=step.get("deps", []), note=step.get("note", ""))
            for step in arguments["steps"]
        ]
        plan = TaskPlan(session_id=session_id, message_id=message_id, intent=intent, steps=steps, base_card=base_card)
        return [
            (task, build_task_content(task.id, SkeletonInputs.from_plan(plan, step)))
            for task, step in plan.expand()
        ]

    def _persist(self, pairs):
        """逐条落库 task 与其 content。"""
        for task, content in pairs:
            self._task_repo.insert(task)
            self._content_repo.insert(content)

    def _finalize(self, pairs):
        """复位意图状态并返回建图完成回执。"""
        self._intent_state.mark_dispatched(pairs[0][0].session_id)
        roles = ", ".join(f"{task.agent_type}#{i}" for i, (task, _) in enumerate(pairs, 1))
        return Suspend(
            f"已创建创作任务图：pipeline={pairs[0][0].pipeline_id}，"
            f"{len(pairs)} 个任务 [{roles}]，等待计划完成"
        )

    def resolve_external(self, session_id: str, signal: str, payload: Optional[dict] = None) -> str:
        """图收敛后的回执：最近一张图成品完成则直给全文与成品标识，否则取消一句话。"""
        tasks = self._task_service.current_pipeline_tasks(session_id)
        finalize_task = next((task for task in tasks if task.agent_type == AgentType.FINALIZE), None)
        if finalize_task is None or finalize_task.status != TaskStatus.FINISHED:
            return CANCELLED_PIPELINE_RECEIPT
        card = cast(PostCard, self._artifacts_repo.load(finalize_task.id).artifacts)
        return render_delivery_receipt(finalize_task.id, card)
