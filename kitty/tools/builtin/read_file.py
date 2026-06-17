"""read_file 工具：读取文件内容。"""

from __future__ import annotations

from kitty.tools.base import Tool, ToolContext


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取文件内容，返回文件的文本。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对于工作目录）"},
            "limit": {"type": "integer", "description": "最多读取的行数（可选）"},
        },
        "required": ["path"],
    }

    def display(self, arguments: dict) -> str:
        path = arguments.get("path") or "(未指定)"
        limit = arguments.get("limit")
        return f"读取文件: {path} (前 {limit} 行)" if limit else f"读取文件: {path}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        try:
            lines = ctx.workspace.safe_path(arguments.get("path", "")).read_text(encoding="utf-8").splitlines()
        except Exception as e:
            return f"Error: {e}"
        limit = arguments.get("limit")
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
