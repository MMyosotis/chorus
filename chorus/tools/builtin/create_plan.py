"""建图工具：解析、校验、整图成型与事务落库全在工具内收口。

对模型是普通工具，主流程只据挂起信号关流本轮。可预料失败返回传由模型自纠，
仅意外异常由派发层兜底。
"""
from __future__ import annotations

from typing import Optional

from pydantic import ValidationError as PydanticValidationError

from chorus.domain.intent import Intent
from chorus.domain.task import (
    StepSpec,
    TaskPlan,
    ValidationError,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.intent_state import IntentStateService
from chorus.tools.framework import Reply, Suspend, Tool, ToolContext, ToolRunResult


class CreatePlanTool(Tool):
    name = "create_plan"
    description = (
        "当用户要创作图文博文时调用，按用户实际自主编排创作步骤；"
        "普通对话直接文本回复不调用本工具。"
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
        content_repo: TaskContentRepository,
        intent_state: IntentStateService,
    ):
        self._task_repo = task_repo
        self._content_repo = content_repo
        self._intent_state = intent_state

    def display(self, arguments: dict) -> str:
        topic = (arguments.get("intent", {}) or {}).get("topic", "")
        return f"创作：{topic or '(未指定主题)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        blocked = self._intent_gate(ctx.session_id)
        if blocked:
            return ToolRunResult(blocked)
        try:
            pairs = self._build_pairs(arguments, ctx.session_id, ctx.message_id)
        except (KeyError, TypeError, PydanticValidationError) as e:
            return ToolRunResult(Reply(f"create_plan 参数缺失或格式错: {e}"))
        except ValidationError as e:
            return ToolRunResult(Reply(e.correction))
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

    def _build_pairs(self, arguments: dict, session_id: str, message_id: Optional[str]):
        """解析 steps、整份 intent 透传（不逐字段拆解）、校验、展开成 (task, content) 对。"""
        intent = Intent.model_validate(arguments["intent"])
        steps = [
            StepSpec(agent_type=step["agent_type"], deps=step.get("deps", []))
            for step in arguments["steps"]
        ]
        return TaskPlan(session_id=session_id, message_id=message_id, intent=intent, steps=steps).expand()

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
        """pipeline 全部跑完后的收尾：复位意图状态，告知模型计划已落地。"""
        state = self._intent_state.patch_status(session_id, "empty")
        return f"计划已完成，所有创作步骤均已落地（version={state.version}）"
