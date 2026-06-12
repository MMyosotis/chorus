from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


WORKDIR = Path.cwd()


@dataclass
class ToolDef:
    """一个工具定义：API schema + 执行 handler"""

    name: str
    description: str
    parameters: dict  # JSON Schema（OpenAI function calling 格式）
    handler: Callable[..., str]


_REGISTRY: dict[str, ToolDef] = {}


def tool(name: str, description: str, parameters: dict):
    """装饰器：将函数注册为工具。"""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
        )
        return fn

    return decorator


def safe_path(p: str) -> Path:
    """确保路径不逃逸工作目录。"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def get_all_tools() -> list[ToolDef]:
    """返回所有已注册的工具定义。"""
    return list(_REGISTRY.values())


def get_tool_schemas() -> list[dict[str, Any]]:
    """返回 OpenAI 格式的 tools 参数列表。"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _REGISTRY.values()
    ]


def dispatch_tool(name: str, arguments: dict) -> str:
    """按名称执行工具，返回字符串结果。"""
    t = _REGISTRY.get(name)
    if t is None:
        return f"Error: unknown tool '{name}'"
    try:
        return t.handler(**arguments)
    except Exception as e:
        return f"Error executing tool '{name}': {e}"
