# chorus/domain/task/activity.py
"""Activity 翻译层：把 subagent ReAct 事件翻译成用户态 ActivityDraft。

纯函数，不碰 DB。围绕 task 活动展示单一概念内聚。模板按 agent_type + tool_name +
event_type 查表生成，文案禁 emoji。工具结构化产物经 activity_meta（来自
DispatchResult.activity_meta，由 ToolRunResult 透传）传入，不从格式化文本反解析。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from chorus.domain.task.models import Narrative
from chorus.domain.task.profiles import AGENT_PROFILES

# 用户可见工具（写 tool_started/tool_done activity）；load_skill 等隐藏
_VISIBLE_TOOLS = {"baidu_search", "generate_image", "output_plan"}


@dataclass(frozen=True)
class ActivityDraft:
    event_type: str
    action_type: str
    role_line: str
    status: str = "running"
    title: Optional[str] = None
    detail_md: Optional[str] = None
    summary_json: Optional[dict] = None
    progress_json: Optional[dict] = None
    artifact_preview_json: Optional[dict] = None


def is_user_visible_tool(tool_name: str) -> bool:
    return tool_name in _VISIBLE_TOOLS


def _enter(agent_type: str) -> str:
    return AGENT_PROFILES[agent_type].enter_line


def started_activity(agent_type: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="started",
        action_type=_started_action(agent_type),
        role_line=_enter(agent_type),
        status="running",
    )


def _started_action(agent_type: str) -> str:
    return {
        "idea": "researching",
        "script": "writing",
        "image": "generating_image",
        "finalize": "organizing",
    }.get(agent_type, "planning")


def tool_started_activity(
    agent_type: str, tool_name: str, arguments: dict, task_metadata: Optional[dict],
) -> Optional[ActivityDraft]:
    if not is_user_visible_tool(tool_name):
        return None
    return ActivityDraft(
        event_type="tool_started",
        action_type=_tool_action(tool_name, agent_type),
        role_line=_tool_started_line(tool_name, arguments),
        status="running",
    )


def _tool_action(tool_name: str, agent_type: str) -> str:
    if tool_name == "baidu_search":
        return "researching"
    if tool_name == "generate_image":
        return "generating_image"
    if tool_name == "output_plan":
        return "planning"
    return "validating"


def _tool_started_line(tool_name: str, arguments: dict) -> str:
    if tool_name == "baidu_search":
        q = (arguments.get("query") or "").strip()
        return f"正在搜索：{q[:30]}" if q else "正在联网搜索"
    if tool_name == "generate_image":
        return "正在生成配图"
    if tool_name == "output_plan":
        return "正在整理计划"
    return "工具调用中"


def tool_done_activity(
    agent_type: str, tool_name: str, arguments: dict,
    activity_meta: Optional[dict], task_metadata: Optional[dict],
    done_images: list[str],
) -> Optional[ActivityDraft]:
    if not is_user_visible_tool(tool_name):
        return None
    if tool_name == "baidu_search":
        return _baidu_done(activity_meta)
    if tool_name == "generate_image":
        return _image_done(activity_meta, task_metadata, done_images)
    if tool_name == "output_plan":
        return ActivityDraft(
            event_type="tool_done", action_type="planning",
            role_line="计划已整理", status="running",
        )
    return None


def _baidu_done(activity_meta: Optional[dict]) -> ActivityDraft:
    refs = (activity_meta or {}).get("refs") or []
    total = len(refs)
    bullets = [
        {"title": r.get("title") or "(无标题)", "url": r.get("url") or ""}
        for r in refs
    ]
    role_line = f"找到 {total} 条参考资料" if total else "没有搜到相关结果"
    return ActivityDraft(
        event_type="tool_done", action_type="researching",
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
        event_type="tool_done", action_type="generating_image",
        role_line=role_line, status="running",
        progress_json=progress_json, artifact_preview_json=preview_json,
    )


def image_progress_preview(
    total: Optional[int], done_images: list[str], running_label: Optional[str] = None,
) -> tuple[Optional[dict], dict]:
    """返 (progress_json, artifact_preview_json)。

    - total 缺失 → progress_json=None（不显示 current/total，避免假仪表盘）。
    - artifact_preview_json 始终列出已生成图。
    """
    items = [{"url": u, "caption": ""} for u in done_images]
    preview = {"type": "images", "items": items}
    if total:
        prog = {
            "type": "steps",
            "current": len(done_images),
            "total": total,
            "unit": "张图",
        }
        return prog, preview
    return None, preview


def awaiting_activity(agent_type: str, narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.awaiting_line if narrative else None) or "产出待你确认"
    return ActivityDraft(
        event_type="awaiting_confirm", action_type="waiting_user",
        role_line=line, status="running",
    )


def done_activity(agent_type: str, narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.done_line if narrative else None) or "本步完成"
    return ActivityDraft(
        event_type="done", action_type="summarizing",
        role_line=line, status="done",
    )


def failed_activity(agent_type: str, error: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="failed", action_type="recovering",
        role_line="这步出了点问题", status="failed",
        detail_md=error,
    )


def retrying_activity(agent_type: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="retrying", action_type="validating",
        role_line="刚才的格式不太对，我重新整理一下", status="warning",
    )
