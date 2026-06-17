"""edit_file 工具：精确替换一次匹配文本。"""

from __future__ import annotations

from kitty.tools.base import Tool, ToolContext


class EditFileTool(Tool):
    name = "edit_file"
    description = "在文件中精确替换一次匹配文本。若 old_text 未找到或出现多次则失败。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对于工作目录）"},
            "old_text": {"type": "string", "description": "要查找并替换的原始文本（必须唯一）"},
            "new_text": {"type": "string", "description": "替换后的新文本"},
        },
        "required": ["path", "old_text", "new_text"],
    }

    def display(self, arguments: dict) -> str:
        return f"编辑文件: {arguments.get('path') or '(未指定)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        path = arguments.get("path", "")
        try:
            file_path = ctx.workspace.safe_path(path)
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error: {e}"
        old_text = arguments.get("old_text", "")
        count = text.count(old_text)
        if count == 0:
            return f"Error: text not found in {path}"
        if count > 1:
            return f"Error: text found {count} times in {path}, must be unique"
        file_path.write_text(text.replace(old_text, arguments.get("new_text", ""), 1), encoding="utf-8")
        return f"Edited {path}"
