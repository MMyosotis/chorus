"""计划展示的纯领域逻辑。"""

from __future__ import annotations


def format_plan_steps(steps: list[str]) -> str:
    """把有序步骤列表格式化为展示文本：『1. …\n2. …』。

    纯领域逻辑：输入字符串列表，输出展示文本，可脱离 DB/HTTP 独立单测。
    """
    lines = []
    for i, step in enumerate(steps, start=1):
        text = (step or "").strip()
        if text:
            lines.append(f"{i}. {text}")
    return "\n".join(lines)
