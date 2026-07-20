"""load_skill 工具：按名称加载技能完整内容。"""

from __future__ import annotations

from chorus.domain.skill import SkillLoader
from chorus.tools.framework import Reply, Tool, ToolContext, ToolRunResult


class LoadSkillTool(Tool):
    name = "load_skill"
    description = (
        "按名称加载技能（skill）的完整内容；可选 path 读技能包内子文件"
        "（如 references/script.md、preview/desktop.html）。可用技能见 system prompt 的技能清单。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要加载的技能名称"},
            "path": {
                "type": "string",
                "description": "技能包内子文件相对路径，如 references/script.md；不传则返回技能完整正文",
            },
        },
        "required": ["name"],
    }
    running_label = "加载技能中"

    def __init__(self, skill_loader: SkillLoader):
        self._skill_loader = skill_loader

    def display(self, arguments: dict) -> str:
        name = arguments.get("name") or "(未指定)"
        path = arguments.get("path")
        return f"加载技能: {name} / {path}" if path else f"加载技能: {name}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        name = arguments.get("name", "")
        path = arguments.get("path") or "SKILL.md"
        content = self._skill_loader.read_file(name, path)
        if content is None:
            return ToolRunResult(Reply(f"Error: skill file '{name}/{path}' not found"))
        return ToolRunResult(Reply(content))
