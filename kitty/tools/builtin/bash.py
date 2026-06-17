"""bash 工具：执行 shell 命令。"""

from __future__ import annotations

import subprocess

from kitty.tools.base import Tool, ToolContext


class BashTool(Tool):
    name = "bash"
    description = "执行 shell 命令并返回 stdout/stderr。可用于文件操作、运行脚本等。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {"type": "integer", "description": "超时秒数（默认 30）", "default": 30},
        },
        "required": ["command"],
    }

    _BLOCKED = ("rm -rf /", "mkfs", "dd if=", "sudo", "shutdown", "reboot")

    def display(self, arguments: dict) -> str:
        cmd = (arguments.get("command") or "").strip()
        return f"执行命令: {cmd or '(空命令)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        command = arguments.get("command", "")
        timeout = arguments.get("timeout", 30)
        if any(b in command for b in self._BLOCKED):
            return "Error: command blocked for safety"
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output[:10000] if output else "(no output)"
