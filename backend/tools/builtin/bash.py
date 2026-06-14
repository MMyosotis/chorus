import subprocess

from backend.tools.base import tool


def _display(args: dict) -> str:
    cmd = (args.get("command") or "").strip()
    return f"执行命令: {cmd or '(空命令)'}"


@tool(
    name="bash",
    description="执行 shell 命令并返回 stdout/stderr。可用于文件操作、运行脚本等。",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数（默认 30）",
                "default": 30,
            },
        },
        "required": ["command"],
    },
    display=_display,
)
def bash(command: str, timeout: int = 30) -> str:
    BLOCKED = {"rm -rf /", "mkfs", "dd if=", "sudo", "shutdown", "reboot"}
    if any(cmd in command for cmd in BLOCKED):
        return "Error: command blocked for safety"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output[:10000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
