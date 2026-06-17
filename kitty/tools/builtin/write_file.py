"""write_file 工具：写入文件。"""

from __future__ import annotations

from kitty.tools.base import Tool, ToolContext


class WriteFileTool(Tool):
    name = "write_file"
    description = "把内容写入文件，必要时自动创建上级目录。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对于工作目录）"},
            "content": {"type": "string", "description": "要写入的内容"},
        },
        "required": ["path", "content"],
    }

    def display(self, arguments: dict) -> str:
        path = arguments.get("path") or "(未指定)"
        content = arguments.get("content") or ""
        return f"写入文件: {path} ({len(content)} 字符)"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        try:
            file_path = ctx.workspace.safe_path(arguments.get("path", ""))
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = arguments.get("content", "")
            file_path.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {arguments.get('path')}"
        except Exception as e:
            return f"Error: {e}"
