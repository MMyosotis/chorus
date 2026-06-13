from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


WORKDIR = Path.cwd()


@dataclass
class ToolDef:
    """一个工具定义：API schema + 执行 handler + 可选的展示文本生成器"""

    name: str
    description: str
    parameters: dict  # JSON Schema（OpenAI function calling 格式）
    handler: Callable[..., str]
    display: Optional[Callable[[dict], str]] = None
    running_label: Optional[str] = None  # 工具运行中时前端状态条上的文案；缺省由前端显示"工具调用中"


_REGISTRY: dict[str, ToolDef] = {}

_DISPLAY_MAX_LEN = 200


def tool(
    name: str,
    description: str,
    parameters: dict,
    display: Optional[Callable[[dict], str]] = None,
    running_label: Optional[str] = None,
):
    """装饰器：将函数注册为工具。

    display: 可选回调，接收已解析的参数 dict，返回单行人类可读描述。
             未提供时，format_tool_display 会回退到工具名。
    running_label: 可选字符串，工具执行期间前端状态条显示的文案（如"图片生成中"）。
                   未提供时前端显示通用的"工具调用中"。
    """

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
            display=display,
            running_label=running_label,
        )
        return fn

    return decorator


def format_tool_display(name: str, arguments: dict) -> str:
    """生成工具调用的人类可读单行描述。

    回退顺序：工具未注册 / 未提供 display / display 抛错 / 返回非字符串或空字符串
    都回退为返回工具名。最终结果保证单行（换行符替换为空格）且长度受限。
    """
    fallback = name or "tool"
    try:
        t = _REGISTRY.get(name)
        if t is None or t.display is None:
            return fallback
        text = t.display(arguments or {})
        if not isinstance(text, str):
            return fallback
        text = text.replace("\n", " ").replace("\r", " ").strip()
        if not text:
            return fallback
        if len(text) > _DISPLAY_MAX_LEN:
            text = text[:_DISPLAY_MAX_LEN] + "…"
        return text
    except Exception:
        return fallback


def get_running_label(name: str) -> Optional[str]:
    """返回工具运行中的状态条文案，未配置返回 None。"""
    t = _REGISTRY.get(name)
    if t is None:
        return None
    return t.running_label


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
