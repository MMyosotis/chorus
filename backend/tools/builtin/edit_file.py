from backend.tools.base import safe_path, tool


def _display(args: dict) -> str:
    path = args.get("path") or "(未指定)"
    return f"编辑文件: {path}"


@tool(
    name="edit_file",
    description="Replace exact text in a file once. Fails if old_text is not found or appears multiple times.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace)",
            },
            "old_text": {
                "type": "string",
                "description": "Exact text to find and replace",
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["path", "old_text", "new_text"],
    },
    display=_display,
)
def edit_file(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            return f"Error: text not found in {path}"
        if count > 1:
            return f"Error: text found {count} times in {path}, must be unique"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"
