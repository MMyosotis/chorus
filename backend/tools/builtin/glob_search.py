import glob as glob_module

from backend.tools.base import WORKDIR, tool


def _display(args: dict) -> str:
    pattern = args.get("pattern") or "(未指定)"
    return f"查找文件: {pattern}"


@tool(
    name="glob",
    description="在工作目录下按 glob 模式查找文件。",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "glob 模式，例如 '**/*.py'、'src/*.ts'",
            },
        },
        "required": ["pattern"],
    },
    display=_display,
)
def glob_search(pattern: str) -> str:
    try:
        results = []
        for match in glob_module.glob(pattern, root_dir=WORKDIR, recursive=True):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"
