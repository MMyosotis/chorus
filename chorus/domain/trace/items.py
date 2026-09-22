"""轨迹条目：来源角色、旁路与用户输入，统一提取现场消息正文。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional

from chorus.domain.prompt.assembly import TaggedSegment, parse_tagged_content
from chorus.domain.task.models import AgentType
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.trace.models import BypassCall, ModelRequest, TraceEntry, UserInput


@dataclass(frozen=True)
class AgentRole:
    """轨迹来源角色：过滤键、页签短名与轮次归属名。"""

    key: str
    label: str
    name: str


SUPERVISOR_ROLE = AgentRole("supervisor", "主编", "主编辑")


def role_for(task_id: Optional[str], agent_type_by_task: dict[str, AgentType]) -> AgentRole:
    """有任务归子角色，其余归主编。"""
    if not task_id:
        return SUPERVISOR_ROLE
    profile = AGENT_PROFILES[agent_type_by_task[task_id]]
    return AgentRole(f"task:{task_id}", profile.short_name, profile.display_name)


@dataclass
class Bypass:
    """一条旁路调用轨迹，完成时间为锚，开始时间按自报时长回推。"""

    key: str
    created_at: float
    role: AgentRole
    payload: BypassCall

    @property
    def start_at(self) -> float:
        return self.created_at - (self.payload.duration_ms or 0) / 1000

    @property
    def end_at(self) -> float:
        return self.created_at


@dataclass
class UserInputItem:
    """显式输入或从请求回溯的用户输入。"""

    key: str
    created_at: float
    text: str
    injections: list[TaggedSegment]


def message_text(content: object) -> str:
    """现场消息正文统一转文本，非字符串正文转 JSON。"""
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False, indent=2)


def user_input_for(request: ModelRequest, created_at: float) -> Optional[UserInputItem]:
    """回溯最后一条用户消息，无可用正文则不生成独立输入。"""
    for index in range(len(request.messages) - 1, -1, -1):
        message = request.messages[index]
        if message.get("role") != "user":
            continue
        raw = message_text(message.get("content"))
        text, injections = parse_tagged_content(raw)
        if not text:
            return None
        return UserInputItem(key=f"{index}:{raw}", created_at=created_at, text=text, injections=injections)
    return None


def build_bypasses(entries: Iterable[TraceEntry], agent_type_by_task: dict[str, AgentType]) -> list[Bypass]:
    """取旁路轨迹按时间排序。"""
    rows = [Bypass(
        key=f"bypass:{entry.created_at}:{entry.source}:{entry.task_id or ''}:{entry.payload.purpose}",
        created_at=entry.created_at,
        role=role_for(entry.task_id, agent_type_by_task),
        payload=entry.payload,
    ) for entry in entries if isinstance(entry.payload, BypassCall)]
    return sorted(rows, key=lambda item: item.created_at)


def build_user_inputs(entries: Iterable[TraceEntry]) -> list[UserInputItem]:
    """取显式用户输入轨迹并反解注入段，按时间排序。"""
    rows = []
    for entry in entries:
        if not isinstance(entry.payload, UserInput):
            continue
        text, injections = parse_tagged_content(entry.payload.content)
        rows.append(UserInputItem(
            key=entry.message_id or f"user:{entry.created_at}",
            created_at=entry.created_at, text=text, injections=injections,
        ))
    return sorted(rows, key=lambda item: item.created_at)
