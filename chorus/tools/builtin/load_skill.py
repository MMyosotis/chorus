"""load_skill 工具：按名称加载技能完整内容。"""

from __future__ import annotations

import json

from chorus.domain.skill import SkillLoader
from chorus.tools.framework import Reply, Tool, ToolContext


class LoadSkillTool(Tool):
    name = "load_skill"
    description = "按名称加载技能（skill）的完整内容。当用户的请求与某个技能的描述匹配时使用。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要加载的技能名称"},
        },
        "required": ["name"],
    }
    running_label = "加载技能中"

    def __init__(self, skill_loader: SkillLoader):
        self._skill_loader = skill_loader

    def display(self, arguments: dict) -> str:
        return f"加载技能: {arguments.get('name') or '(未指定)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> Reply:
        name = arguments.get("name", "")
        skill = self._skill_loader.get(name)
        if skill is None:
            available = [skill.name for skill in self._skill_loader.list_summaries()]
            return Reply(f"Error: skill '{name}' not found. Available skills: {json.dumps(available)}")
        return Reply(skill.full_content)
