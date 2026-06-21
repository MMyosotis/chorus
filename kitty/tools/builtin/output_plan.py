"""output_plan 工具：向用户展示执行计划。"""

from __future__ import annotations

from kitty.tools.framework import Tool, ToolContext


def format_plan_steps(steps: list[str]) -> str:
    """把有序步骤列表格式化为展示文本：『1. …\n2. …』。"""
    lines = []
    for i, step in enumerate(steps, start=1):
        text = (step or "").strip()
        if text:
            lines.append(f"{i}. {text}")
    return "\n".join(lines)


class OutputPlanTool(Tool):
    name = "output_plan"
    description = "向用户展示执行计划。steps 为按执行顺序的步骤描述字符串列表。"
    parameters = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "按执行顺序的步骤描述列表",
            },
        },
        "required": ["steps"],
    }
    running_label = "制定计划"

    def display(self, arguments: dict) -> str:
        steps = arguments.get("steps") or []
        n = len(steps) if isinstance(steps, list) else 0
        return f"规划 {n} 个步骤"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        steps = arguments.get("steps") or []
        if not isinstance(steps, list):
            steps = []
        return format_plan_steps(steps)
