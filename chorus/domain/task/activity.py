"""把子 agent 事件翻译成用户可见的活动卡片。

纯函数，不碰数据库，按角色与工具查模板生成。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Union

from chorus.domain.task.models import (
    FailedPayload,
    ImageProgressPayload,
    Narrative,
    SearchResultsPayload,
)
from chorus.domain.task.profiles import AGENT_PROFILES

# 通用态文案
_FAILED_LINE = "这步出了点问题"
_RETRYING_LINE = "刚才的格式不太对，我重新整理一下"

# 活动业务载荷判别联合，按 event_type 取对应类型
ActivityPayload = Union[SearchResultsPayload, ImageProgressPayload, FailedPayload]

# 载荷类型注册表，(event_type, tool_name) → dataclass 类
PAYLOAD_TYPES: dict[tuple[str, Optional[str]], type] = {
    ("failed", None): FailedPayload,
    ("tool_done", "baidu_search"): SearchResultsPayload,
    ("tool_done", "generate_image"): ImageProgressPayload,
}


def build_payload(
    event_type: str, tool_name: Optional[str], raw: Optional[dict],
) -> Optional[ActivityPayload]:
    """按 (event_type, tool_name) 查注册表把原始数据还原成强类型载荷。

    None 原数据对应无载荷。未知组合 KeyError 上抛，由调用方兜底。
    """
    return None if raw is None else PAYLOAD_TYPES[(event_type, tool_name)](**raw)


@dataclass(frozen=True)
class ActivityDraft:
    event_type: str
    role_line: str
    status: str = "running"
    tool_name: Optional[str] = None
    payload: Optional[ActivityPayload] = None


def started_activity(agent_type: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="started",
        role_line=_enter(agent_type),
        status="running",
    )


def tool_started_activity(tool_name: str, arguments: dict) -> ActivityDraft:
    return ActivityDraft(
        event_type="tool_started",
        role_line=_tool_started_line(tool_name, arguments),
        status="running",
        tool_name=tool_name,
    )


def tool_done_activity(
    tool_name: str,
    activity_meta: Optional[dict],
    progress_total: Optional[int],
    done_images: list[str],
) -> Optional[ActivityDraft]:
    fn = _DONE_TRANSLATORS.get(tool_name)
    return fn(activity_meta, progress_total, done_images) if fn else None


def awaiting_activity(narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.awaiting_line if narrative else None) or "产出待你确认"
    return ActivityDraft(
        event_type="awaiting_confirm",
        role_line=line, status="running",
    )


def done_activity(narrative: Optional[Narrative]) -> ActivityDraft:
    line = (narrative.done_line if narrative else None) or "本步完成"
    return ActivityDraft(
        event_type="done",
        role_line=line, status="done",
    )


def failed_activity(error: str) -> ActivityDraft:
    return ActivityDraft(
        event_type="failed",
        role_line=_FAILED_LINE, status="failed",
        payload=FailedPayload(detail_md=error),
    )


def retrying_activity() -> ActivityDraft:
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
    activity_meta: Optional[dict], _progress_total: Optional[int],
    _done_images: list[str],
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
        tool_name="baidu_search",
        payload=SearchResultsPayload(total=total, bullets=bullets),
    )


def _image_done(
    activity_meta: Optional[dict], progress_total: Optional[int],
    done_images: list[str],
) -> ActivityDraft:
    url = (activity_meta or {}).get("url") or ""
    all_images = done_images + ([url] if url else [])
    current, total = image_progress(progress_total, all_images)
    items = [{"url": u, "caption": ""} for u in all_images]
    n = len(all_images)
    role_line = f"已生成 {n} 张配图" if n else "配图生成完成"
    return ActivityDraft(
        event_type="tool_done",
        role_line=role_line, status="running",
        tool_name="generate_image",
        payload=ImageProgressPayload(current=current, total=total, items=items),
    )


def _output_plan_done(
    _activity_meta: Optional[dict], _progress_total: Optional[int],
    _done_images: list[str],
) -> ActivityDraft:
    return ActivityDraft(
        event_type="tool_done",
        role_line="计划已整理", status="running",
        tool_name="output_plan",
    )


_DONE_TRANSLATORS: dict[str, Callable[..., ActivityDraft]] = {
    "baidu_search": _baidu_done,
    "generate_image": _image_done,
    "output_plan": _output_plan_done,
}


def image_progress(total: Optional[int], done_images: list[str]) -> tuple[int, Optional[int]]:
    """配图进度：current=已生成数，total 未知时返 None。"""
    return len(done_images), total
