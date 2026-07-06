"""SSE 事件 sealed 联合断言：type 判别 / 序列化往返 / 必填校验 / BusyEvent 契约。

11 种事件各持唯一 type 字面量、frozen + extra=forbid、JSON 经联合类型往返、缺必填抛错。
BusyEvent 携带 content（业务忙非错误，supervisor 创作准入拒绝时回传）。
"""
from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from chorus.domain.events import (
    BusyEvent,
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    ReasoningDoneEvent,
    ReasoningEvent,
    SseEvent,
    TitleUpdateEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    TraceEvent,
)
from chorus.domain.trace import TracePhase


_FIXTURES = [
    (MessageStartEvent, {"id": "m1"}, "message_start"),
    (ReasoningEvent, {"content": "想"}, "reasoning"),
    (ReasoningDoneEvent, {"duration_ms": 12}, "reasoning_done"),
    (TokenEvent, {"content": "hi"}, "token"),
    (ToolCallEvent, {"id": "c1", "name": "gen", "arguments": {"a": 1}, "display": "生成"}, "tool_call"),
    (ToolResultEvent, {"tool_call_id": "c1", "name": "gen", "content": "ok", "duration_ms": 5}, "tool_result"),
    (TraceEvent, {"phase": TracePhase.MODEL_REQUEST, "created_at": 1.0, "payload": {"k": "v"}}, "trace"),
    (TitleUpdateEvent, {"id": "s1", "title": "夏日晚风"}, "title_update"),
    (DoneEvent, {}, "done"),
    (ErrorEvent, {"content": "炸了"}, "error"),
    (BusyEvent, {"content": "创作中"}, "busy"),
]


def test_each_event_has_distinct_type():
    seen = set()
    for cls, kwargs, expected in _FIXTURES:
        ev = cls(**kwargs)
        assert ev.type == expected
        assert expected not in seen  # 各类型唯一
        seen.add(expected)
    assert len(seen) == len(_FIXTURES)


def test_model_dump_json_roundtrips_via_sse_union():
    adapter = TypeAdapter(SseEvent)
    for cls, kwargs, _expected in _FIXTURES:
        ev = cls(**kwargs)
        # JSON 序列化后经联合类型反序列化，同类同值
        rebuilt = adapter.validate_json(ev.model_dump_json())
        assert type(rebuilt) is cls
        assert rebuilt.model_dump() == ev.model_dump()


def test_required_fields_enforced():
    with pytest.raises(ValidationError):
        TokenEvent()  # 缺正文
    with pytest.raises(ValidationError):
        MessageStartEvent()  # 缺标识
    with pytest.raises(ValidationError):
        ToolCallEvent(id="c1", name="gen", display="x")  # 缺参数


def test_frozen_and_extra_forbidden():
    ev = TokenEvent(content="hi")
    with pytest.raises(ValidationError):
        ev.content = "mut"  # frozen
    with pytest.raises(ValidationError):
        TokenEvent(content="hi", rogue="no")  # extra forbidden


def test_busy_event_carries_content():
    ev = BusyEvent(content="该会话有创作任务进行中")
    assert ev.type == "busy"
    assert ev.content == "该会话有创作任务进行中"


def test_trace_event_phase_serializes_as_enum_value():
    ev = TraceEvent(phase=TracePhase.TOOL_CALL, created_at=2.5, payload={})
    dump = ev.model_dump()
    assert dump["phase"] == TracePhase.TOOL_CALL
    j = ev.model_dump_json()
    assert '"tool_call"' in j


def test_tool_call_event_optional_running_label():
    ev = ToolCallEvent(id="c1", name="gen", arguments={}, display="x")
    assert ev.running_label is None  # 可选字段默认 None
    ev2 = ToolCallEvent(id="c1", name="gen", arguments={}, display="x", running_label="运行中")
    assert ev2.running_label == "运行中"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
