"""建图工具：解析、校验、整图成型与事务落库全在工具内收口。

对模型是普通工具，主流程只据终止信号结束本轮。可预料失败返回传由模型自纠，
仅意外异常由派发层兜底。
"""
from __future__ import annotations

import time

from chorus.domain.task import (
    CreationIntent,
    StepSpec,
    ValidationError,
    validate_steps,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.intent_state import IntentStateService
from chorus.tools.framework import Reply, Terminal, Tool, ToolContext


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
            "friendly_reply": {
                "type": "string",
                "description": "建任务前对用户的友好回复，会作为流程节拍气泡展示",
            },
            "intent": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "创作主题/方向"},
                    "style": {"type": "string", "description": "风格倾向，如轻松/专业/种草"},
                    "image_count": {"type": "integer", "description": "配图数量，默认 3"},
                    "extra": {"type": "object", "description": "其它要求"},
                },
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
                        "focus": {"type": "string", "description": "本步针对本次任务的具体指令"},
                    },
                    "required": ["agent_type", "deps", "focus"],
                },
            },
        },
        "required": ["thought", "friendly_reply", "intent", "steps"],
    }
    running_label = "编排创作任务"

    def __init__(
        self,
        task_repo: TaskRepository,
        content_repo: TaskContentRepository,
        intent_state: IntentStateService | None = None,
    ):
        self._task_repo = task_repo
        self._content_repo = content_repo
        self._intent_state = intent_state

    def display(self, arguments: dict) -> str:
        topic = (arguments.get("intent", {}) or {}).get("topic", "")
        return f"创作：{topic or '(未指定主题)'}"

    def run(self, arguments: dict, ctx: ToolContext):  # -> ToolOutcome
        if not ctx.session_id:
            return Reply("create_plan 需要 session_id")
        if self._intent_state is not None and not self._intent_state.is_confirmed(ctx.session_id):
            state = self._intent_state.get(ctx.session_id)
            return Reply(
                "create_plan blocked: 当前意图尚未由用户确认。"
                f"intent_status={state.intent_status}。请先继续澄清意图，"
                "或在 ready_to_confirm 后等待用户确认。"
            )
        try:
            intent_in = arguments["intent"]
            intent = CreationIntent(
                topic=intent_in["topic"],
                style=intent_in.get("style", ""),
                image_count=intent_in.get("image_count", 3),
                extra=intent_in.get("extra", {}),
            )

            steps = [
                StepSpec(agent_type=step["agent_type"], deps=step.get("deps", []), focus=step["focus"])
                for step in arguments["steps"]
            ]
            validate_steps(steps)

            now = time.time()
            pairs = intent.expand_to_tasks(steps, ctx.session_id, now)
        except (KeyError, TypeError) as e:
            return Reply(f"create_plan 参数缺失或格式错: {e}")
        except ValidationError as e:
            return Reply(e.correction)

        for task, content in pairs:
            self._task_repo.insert(task)
            self._content_repo.insert(content)

        if self._intent_state is not None:
            self._intent_state.mark_dispatched(ctx.session_id)

        roles = ", ".join(f"{task.agent_type}#{i}" for i, (task, _) in enumerate(pairs, 1))
        return Terminal(
            f"已创建创作任务图：pipeline={pairs[0][0].pipeline_id}，"
            f"{len(pairs)} 个任务 [{roles}]，等待计划完成"
        )
