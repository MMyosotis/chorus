"""轨迹视图成品行：时间线行模型与最终 dict 投影，含文本格式化与标签词表。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import ClassVar, Optional

from chorus.domain.prompt.assembly import parse_tagged_content
from chorus.domain.trace.aggregation import Call, ToolExecution
from chorus.domain.trace.items import Bypass, UserInputItem, message_text
from chorus.domain.trace.models import ModelResponse

_BYPASS_PURPOSE_LABELS = {
    "title": "生成标题",
    "summary": "历史摘要",
    "suggestion": "输入建议",
    "aside": "任务旁白",
    "memory_extract": "记忆提取",
    "memory_merge": "记忆整理",
    "memory_recall": "记忆召回",
}

_STATUS_LABELS = {"success": "成功", "error": "失败", "pending": "进行中"}

_MESSAGE_ROLE_LABELS = {"system": "sys", "assistant": "ass"}

_TOOL_WRAPPER = re.compile(r"^<(tool_result|error)>\s*([\s\S]*?)\s*</\1>$")


def _short_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _pretty_json(content: str) -> Optional[str]:
    """形如 JSON 的字符串美化缩进，否则原样返回。"""
    trimmed = content.strip()
    if not trimmed.startswith(("{", "[")):
        return None
    try:
        return json.dumps(json.loads(trimmed), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return None


def _strip_tool_wrapper(raw: str) -> str:
    return _TOOL_WRAPPER.sub(r"\2", raw)


def _tool_call_arguments(tool_call: dict) -> str:
    raw = tool_call.get("function", {}).get("arguments")
    if not isinstance(raw, str):
        return ""
    return _pretty_json(raw) or raw


def toolback_tools(executions: list[ToolExecution]) -> list[dict]:
    """回填行的工具成品行：正文剥包装、JSON 美化。"""
    rows = []
    for execution in executions:
        result = execution.result
        content = _strip_tool_wrapper(result.content)
        rows.append({
            "id": execution.tool_call_id, "name": execution.name, "display": execution.display,
            "duration_ms": result.duration_ms,
            "status": result.status, "status_label": _STATUS_LABELS[result.status],
            "content": content, "pretty": _pretty_json(content),
        })
    return rows


def _user_message_row(role: str, message: dict) -> dict:
    """user/system 消息成品行：正文反解出注入段。"""
    text, injections = parse_tagged_content(message_text(message.get("content")))
    return {
        "role": role, "role_label": _MESSAGE_ROLE_LABELS.get(role, role),
        "preview": text, "text": text,
        "injections": [{"label": seg.label, "content": seg.content} for seg in injections],
    }


def _tool_message_row(message: dict, tool_name_by_id: dict[str, str]) -> dict:
    """tool 消息成品行：预览优先显示工具名，正文剥包装。"""
    raw = message_text(message.get("content"))
    preview = tool_name_by_id.get(message["tool_call_id"]) or raw
    return {
        "role": "tool", "role_label": "tool",
        "preview": preview, "content": _strip_tool_wrapper(raw),
    }


def _assistant_preview(content: str, reasoning: str, tool_calls: list) -> str:
    if content:
        return content
    if reasoning:
        return "无正文 · think"
    if tool_calls:
        return f"无正文 · {len(tool_calls)} 个工具调用"
    return ""


def _assistant_message_row(message: dict) -> dict:
    """assistant 消息成品行：正文 + 思考段 + 工具调用明细。"""
    content = message_text(message.get("content"))
    reasoning = message.get("reasoning_content") or ""
    tool_calls = message.get("tool_calls") or []
    return {
        "role": "assistant", "role_label": _MESSAGE_ROLE_LABELS["assistant"],
        "preview": _assistant_preview(content, reasoning, tool_calls),
        "content": content, "reasoning_content": reasoning,
        "tool_calls": [{
            "id": call.get("id"),
            "name": call.get("function", {}).get("name"),
            "args_pretty": _tool_call_arguments(call),
        } for call in tool_calls],
    }


def _dump_request_message(message: dict, tool_name_by_id: dict[str, str]) -> dict:
    """单条现场消息的成品行：按角色分派分形。"""
    role = message["role"]
    if role in ("user", "system"):
        return _user_message_row(role, message)
    if role == "tool":
        return _tool_message_row(message, tool_name_by_id)
    return _assistant_message_row(message)


@dataclass
class TimelineRow:
    """时间线行基类：轮次归属与统一时间区间。"""

    turn: int
    created_at: float

    @property
    def start_at(self) -> float:
        return self.created_at

    @property
    def end_at(self) -> float:
        return self.created_at

    def dump(self) -> dict:
        raise NotImplementedError


@dataclass
class UserRow(TimelineRow):
    """用户输入行：显式轨迹或从请求回溯。"""

    item: UserInputItem
    kind: ClassVar[str] = "user"

    def dump(self) -> dict:
        return {
            "kind": self.kind, "key": self.item.key, "created_at": self.created_at, "turn": self.turn,
            "text": self.item.text,
            "injections": [{"label": seg.label, "content": seg.content} for seg in self.item.injections],
        }


@dataclass
class BypassRow(TimelineRow):
    """旁路调用行。"""

    item: Bypass
    kind: ClassVar[str] = "bypass"

    @property
    def start_at(self) -> float:
        return self.item.start_at

    @property
    def end_at(self) -> float:
        return self.item.end_at

    def dump(self) -> dict:
        payload = self.item.payload
        return {
            "kind": self.kind, "key": self.item.key, "created_at": self.created_at, "turn": self.turn,
            "agent_name": self.item.role.name,
            "purpose_label": _BYPASS_PURPOSE_LABELS.get(payload.purpose, payload.purpose),
            "status": payload.status,
            "status_label": _STATUS_LABELS[payload.status],
            "duration_ms": payload.duration_ms,
            "model": payload.model,
            "max_tokens": payload.max_tokens,
            "prompt": payload.prompt,
            "content": payload.content,
            "error": payload.error,
            "usage": payload.usage.model_dump() if payload.usage else None,
            "cost_cny": payload.cost_cny,
        }


@dataclass
class LoopRow(TimelineRow):
    """模型调用行。"""

    call: Call
    tool_name_by_id: dict[str, str]
    kind: ClassVar[str] = "loop"

    @property
    def end_at(self) -> float:
        return self.call.end_at

    def _request_data(self) -> dict:
        request = self.call.request
        return {
            "model": request.model,
            "messages": [_dump_request_message(message, self.tool_name_by_id) for message in request.messages],
            "tools": [{
                "name": schema["function"]["name"],
                "description": schema["function"]["description"]}
                for schema in request.tools
            ],
            "raw": request.model_dump(),
        }

    def _response_data(self, response: ModelResponse) -> dict:
        return {
            "thinking_segments": [segment.model_dump() for segment in response.thinking_segments],
            "content": response.content,
            "tools": [{
                "id": execution.tool_call_id,
                "name": execution.name,
                "arguments_pretty": _short_json(execution.arguments)}
                for execution in self.call.tools
            ],
            "raw": response.model_dump(),
        }

    def _result_fields(self) -> dict:
        response = self.call.response
        if response is None:
            return {
                "status": "pending", "duration_ms": None, "thinking_ms": 0,
                "usage": None, "cost_cny": None, "has_output": False, "response": None,
            }
        return {
            "status": response.status,
            "duration_ms": response.duration_ms,
            "thinking_ms": sum(segment.duration_ms for segment in response.thinking_segments),
            "usage": response.usage.model_dump() if response.usage else None,
            "cost_cny": response.cost_cny,
            "has_output": bool(response.content or response.tool_calls or response.thinking_segments),
            "response": self._response_data(response),
        }

    def dump(self) -> dict:
        result_fields = self._result_fields()
        return {
            "kind": self.kind, "key": self.call.key, "created_at": self.created_at, "turn": self.turn,
            "agent_name": self.call.role.name,
            "model": self.call.request.model,
            "request": self._request_data(),
            **result_fields,
            "status_label": _STATUS_LABELS[result_fields["status"]],
        }


@dataclass
class ToolbackRow(TimelineRow):
    """工具结果回传行：按当前请求的关联标识展示结果事件。"""

    tools: list[dict]
    kind: ClassVar[str] = "toolback"

    @property
    def total_ms(self) -> float:
        return sum(tool["duration_ms"] for tool in self.tools)

    def dump(self) -> dict:
        return {
            "kind": self.kind, "created_at": self.created_at, "turn": self.turn,
            "total_ms": self.total_ms, "tools": self.tools,
        }
