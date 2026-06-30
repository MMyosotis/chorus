# kitty/tools/builtin/create_plan.py
"""create_plan 工具：建图副作用单元——解析+校验+整图成型+事务落库，全在工具内收口。

对模型是普通工具（有 schema、被 dispatch、有 trace）；建图全过程（expand + insert）
归本工具，主流程只据 Terminal 终止本轮、不认载荷类型。可预料失败（参数缺失/校验错/
落库失败）返 Reply(correction) 由模型自纠；仅无法预料的意外异常才由 dispatch 兜底
（fail-open 转错误 Reply），对齐「工具可预料失败内部收口」约定。
"""
from __future__ import annotations

import time
from typing import Callable

from chorus.domain.task import (
    CreationIntent,
    StepSpec,
    ValidationError,
    expand_pipeline,
    validate_steps,
)
from chorus.repo.connection import ConnectionFactory
from chorus.repo.task import TaskRepository
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
        conn: ConnectionFactory,
        clock: Callable[[], float] = time.time,
    ):
        self._task_repo = task_repo
        self._conn = conn
        self._clock = clock

    def display(self, arguments: dict) -> str:
        topic = (arguments.get("intent", {}) or {}).get("topic", "")
        return f"创作：{topic or '(未指定主题)'}"

    def run(self, arguments: dict, ctx: ToolContext):  # -> ToolOutcome
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

            now = self._clock()
            tasks = expand_pipeline(intent, steps, ctx.session_id, now)
        except (KeyError, TypeError) as e:
            return Reply(f"create_plan 参数缺失或格式错: {e}")
        except ValidationError as e:
            return Reply(e.correction)

        try:
            with self._conn.transaction():
                for task in tasks:
                    self._task_repo.insert(task)
        except Exception as e:
            return Reply(f"建图落库失败，请重试: {e}")

        roles = ", ".join(f"{task.agent_type}#{task.seq}" for task in tasks)
        return Terminal(
            f"已创建创作任务图：pipeline={tasks[0].pipeline_id}，"
            f"{len(tasks)} 个任务 [{roles}]，调度器将自动执行"
        )
