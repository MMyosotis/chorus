# kitty/tools/builtin/create_plan.py
"""create_plan 工具：声明型工具——只解析+纯校验+声明走向，不执行建图重副作用。

对模型是普通工具（有 schema、被 dispatch、有 trace）；建图副作用（expand + insert）
归编排层 supervisor（跨概念协调，且 run 是 sync 无法 yield SSE）。校验失败返
Reply(correction) 由模型自纠；成功返 Terminal(PlanRequest) 触发 supervisor 建图。
"""
from __future__ import annotations

from kitty.domain.task import (
    CreationIntent,
    PlanRequest,
    StepSpec,
    ValidationError,
    validate_steps,
)
from kitty.tools.framework import Reply, Terminal, Tool, ToolContext

_SUMMARY = "已创建创作任务图，调度器将自动执行"


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
                StepSpec(agent_type=s["agent_type"], deps=s.get("deps", []), focus=s["focus"])
                for s in arguments["steps"]
            ]
            validate_steps(steps)
        except (KeyError, TypeError) as e:
            return Reply(f"create_plan 参数缺失或格式错: {e}")
        except ValidationError as e:
            return Reply(e.correction)
        return Terminal(PlanRequest(intent=intent, steps=steps), summary=_SUMMARY)
