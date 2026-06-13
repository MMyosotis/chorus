import json

from backend.tools.base import tool


def _display(args: dict) -> str:
    name = args.get("name") or "(未指定)"
    return f"加载技能: {name}"


@tool(
    name="load_skill",
    description="Load the full content of a skill by name. Use this when the user's request matches a skill's description.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the skill to load",
            },
        },
        "required": ["name"],
    },
    display=_display,
)
def load_skill(name: str) -> str:
    from backend.skills import get_skill_loader

    loader = get_skill_loader()
    skill = loader.get_skill(name)
    if skill is None:
        available = loader.list_names()
        return f"Error: skill '{name}' not found. Available skills: {json.dumps(available)}"
    return skill.full_content
