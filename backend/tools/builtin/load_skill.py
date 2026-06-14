import json

from backend.tools.base import tool


def _display(args: dict) -> str:
    name = args.get("name") or "(未指定)"
    return f"加载技能: {name}"


@tool(
    name="load_skill",
    description="按名称加载技能（skill）的完整内容。当用户的请求与某个技能的描述匹配时使用。",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "要加载的技能名称",
            },
        },
        "required": ["name"],
    },
    display=_display,
    running_label="加载技能中",
)
def load_skill(name: str) -> str:
    from backend.skills import get_skill_loader

    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if skill is None:
        available = loader.list_names()
        return f"Error: skill '{name}' not found. Available skills: {json.dumps(available)}"
    return skill.full_content
