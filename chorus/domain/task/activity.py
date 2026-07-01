"""把子 agent 事件翻译成用户可见的活动卡片。

纯函数，不碰数据库，按角色与工具查模板生成。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from chorus.domain.task.models import Narrative
from chorus.domain.task.profiles import AGENT_PROFILES

# 用户可见工具
_VISIBLE_TOOLS = {"baidu_search", "generate_image", "output_plan"}

# 通用态文案
_FAILED_LINE = "这步出了点问题"
_RETRYING_LINE = "刚才的格式不太对，我重新整理一下"


@dataclass(frozen=True)
class ActivityDraft:
    event_type: str
    role_line: str
    status: str = "running"
    detail_md: Optional[str] = None
    summary_json: Optional[dict] = None
    progress_json: Optional[dict] = None
    artifact_preview_json: Optional[dict] = None


def is_user_visible_tool(tool_name: str) -> bool:
    return tool_name in _VISIBLE_TOOLS


def started_activity(agent_type: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="started",
        role_line=_enter(agent_type),
        status="running",
    )


def tool_started_activity(
    agent_type: str, tool_name: str, arguments: dict,
) -> Optional[ActivityDraft]:
    if not is_user_visible_tool(tool_name):
        return None
    return ActivityDraft(
        event_type="tool_started",
        role_line=_tool_started_line(tool_name, arguments),
        status="running",
    )


def tool_done_activity(
    agent_type: str, tool_name: str,
    activity_meta: Optional[dict], task_metadata: Optional[dict],
    done_images: list[str],
) -> Optional[ActivityDraft]:
    if not is_user_visible_tool(tool_name):
        return None
    fn = _DONE_TRANSLATORS.get(tool_name)
    return fn(activity_meta, task_metadata, done_images) if fn else None


def awaiting_activity(agent_type: str, narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.awaiting_line if narrative else None) or "产出待你确认"
    return ActivityDraft(
        event_type="awaiting_confirm",
        role_line=line, status="running",
    )


def done_activity(agent_type: str, narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.done_line if narrative else None) or "本步完成"
    return ActivityDraft(
        event_type="done",
        role_line=line, status="done",
    )


def failed_activity(agent_type: str, error: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="failed",
        role_line=_FAILED_LINE, status="failed",
        detail_md=error,
    )


def retrying_activity(agent_type: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="retrying",
        role_line=_RETRYING_LINE, status="warning",
    )


def _enter(agent_type: str) -> str:
    return AGENT_PROFILES[agent_type].enter_line


def _static_started(line: str) -> Callable[[dict], str]:
    """生成固定台词，忽略入参。"""
    return lambda _args: line


def _search_started(args: dict) -> str:
    """搜索类工具的台词，截取查询词前缀，无词走兜底。"""
    q = (args.get("query") or "").strip()
    return f"正在搜索：{q[:30]}" if q else "正在联网搜索"


_STARTED_LINES: dict[str, Callable[[dict], str]] = {
    "baidu_search": _search_started,
    "generate_image": _static_started("正在生成配图"),
    "output_plan": _static_started("正在整理计划"),
}


def _tool_started_line(tool_name: str, arguments: dict) -> str:
    fn = _STARTED_LINES.get(tool_name)
    return fn(arguments) if fn else "工具调用中"


def _baidu_done(
    activity_meta: Optional[dict], _task_metadata: Optional[dict], _done_images: list[str],
) -> ActivityDraft:
    refs = (activity_meta or {}).get("refs") or []
    total = len(refs)
    bullets = [
        {"title": r.get("title") or "(无标题)", "url": r.get("url") or ""}
        for r in refs
    ]
    role_line = f"找到 {total} 条参考资料" if total else "没有搜到相关结果"
    return ActivityDraft(
        event_type="tool_done",
        role_line=role_line, status="running",
        summary_json={"type": "search_results", "total": total, "bullets": bullets},
    )


def _image_done(
    activity_meta: Optional[dict], task_metadata: Optional[dict],
    done_images: list[str],
) -> ActivityDraft:
    url = (activity_meta or {}).get("url") or ""
    all_images = done_images + ([url] if url else [])
    progress_json, preview_json = image_progress_preview(
        (task_metadata or {}).get("progress_total"),
        all_images,
    )
    n = len(all_images)
    role_line = f"已生成 {n} 张配图" if n else "配图生成完成"
    return ActivityDraft(
        event_type="tool_done",
        role_line=role_line, status="running",
        progress_json=progress_json, artifact_preview_json=preview_json,
    )


def _output_plan_done(
    _activity_meta: Optional[dict], _task_metadata: Optional[dict], _done_images: list[str],
) -> ActivityDraft:
    return ActivityDraft(
        event_type="tool_done",
        role_line="计划已整理", status="running",
    )


_DONE_TRANSLATORS: dict[str, Callable[..., ActivityDraft]] = {
    "baidu_search": _baidu_done,
    "generate_image": _image_done,
    "output_plan": _output_plan_done,
}


def image_progress_preview(
    total: Optional[int], done_images: list[str],
) -> tuple[Optional[dict], dict]:
    """生成配图进度与预览。总数未知时不显示进度，避免假仪表盘。"""
    items = [{"url": u, "caption": ""} for u in done_images]
    preview = {"type": "images", "items": items}
    if total:
        prog = {"type": "steps", "current": len(done_images), "total": total, "unit": "张图"}
        return prog, preview
    return None, preview
