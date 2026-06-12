from backend.tools.base import dispatch_tool, get_all_tools, get_tool_schemas  # noqa: F401


def _ensure_loaded():
    """触发工具注册。"""
    import backend.tools.builtin  # noqa: F401


_ensure_loaded()
