"""glob 工具：按 glob 模式查找文件。"""

from __future__ import annotations

import glob as glob_module

from kitty.tools.base import Tool, ToolContext


class GlobSearchTool(Tool):
    name = "glob"
    description = "在工作目录下按 glob 模式查找文件。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "glob 模式，例如 '**/*.py'、'src/*.ts'"},
        },
        "required": ["pattern"],
    }

    def display(self, arguments: dict) -> str:
        return f"查找文件: {arguments.get('pattern') or '(未指定)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        pattern = arguments.get("pattern", "")
        root = ctx.workspace.root
        try:
            results = []
            for match in glob_module.glob(pattern, root_dir=root, recursive=True):
                if (root / match).resolve().is_relative_to(root):
                    results.append(match)
            return "\n".join(results) if results else "(no matches)"
        except Exception as e:
            return f"Error: {e}"
