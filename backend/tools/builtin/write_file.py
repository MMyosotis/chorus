from backend.tools.base import safe_path, tool


def _display(args: dict) -> str:
    path = args.get("path") or "(未指定)"
    content = args.get("content") or ""
    return f"写入文件: {path} ({len(content)} 字符)"


@tool(
    name="write_file",
    description="把内容写入文件，必要时自动创建上级目录。",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径（相对于工作目录）",
            },
            "content": {
                "type": "string",
                "description": "要写入的内容",
            },
        },
        "required": ["path", "content"],
    },
    display=_display,
)
def write_file(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"
