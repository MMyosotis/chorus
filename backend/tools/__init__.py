from backend.tools.base import (  # noqa: F401
    dispatch_tool,
    format_tool_display,
    get_all_tools,
    get_running_label,
    get_tool_schemas,
)


def _ensure_loaded():
    """触发工具注册。"""
    import backend.tools.builtin  # noqa: F401


_ensure_loaded()
