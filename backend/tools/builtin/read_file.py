from backend.tools.base import safe_path, tool


@tool(
    name="read_file",
    description="Read file contents. Returns the text content of a file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (optional)",
            },
        },
        "required": ["path"],
    },
)
def read_file(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
