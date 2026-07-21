"""list_skill 工具：列技能包内全部文件相对路径。"""

from __future__ import annotations

from chorus.domain.skill import SkillLoader
from chorus.tools.framework import Reply, Tool, ToolContext, ToolRunResult


class ListSkillTool(Tool):
    name = "list_skill"
    description = "按名称列出技能（skill）包内的全部文件相对路径。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要列出文件的技能名称"},
        },
        "required": ["name"],
    }
    running_label = "列出技能文件"

    def __init__(self, skill_loader: SkillLoader):
        self._skill_loader = skill_loader

    def display(self, arguments: dict) -> str:
        return f"列出技能文件: {arguments.get('name') or '(未指定)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        name = arguments.get("name", "")
        files = self._skill_loader.list_files(name)
        if files is None:
            return ToolRunResult(Reply(f"Error: skill '{name}' not found"))
        return ToolRunResult(Reply("\n".join(files) or "(空技能包)"))