import subprocess

from backend.tools.base import tool


@tool(
    name="bash",
    description="Run a shell command and return stdout/stderr. Use for file operations, running scripts, etc.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 30)",
                "default": 30,
            },
        },
        "required": ["command"],
    },
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
