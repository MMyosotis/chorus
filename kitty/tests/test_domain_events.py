# kitty/tests/test_domain_events.py
"""SSE 事件 sealed 联合断言：type 判别 / 序列化往返 / 必填校验 / TaskPlanCreated 契约。

覆盖 ``kitty/domain/events.py``：11 种 SSE 事件各持有唯一 type 字面量、frozen + extra=forbid、
model_dump_json 经 SseEvent discriminated union 往返、缺必填抛 ValidationError。
TaskPlanCreatedEvent 携带 pipeline_id + tasks（[{id, agent_type, seq, status}]）。

运行：``.venv/bin/python -m kitty.tests.test_domain_events``
"""
from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from kitty.domain.events import (
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    ReasoningDoneEvent,
    ReasoningEvent,
    SseEvent,
    TaskPlanCreatedEvent,
    TitleUpdateEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    TraceEvent,
)
from kitty.domain.trace import TracePhase


# (事件类, 构造所需 kwargs, 期望 type 字面量)
_FIXTURES = [
    (MessageStartEvent, {"id": "m1"}, "message_start"),
    (ReasoningEvent, {"content": "想"}, "reasoning"),
    (ReasoningDoneEvent, {"duration_ms": 12}, "reasoning_done"),
    (TokenEvent, {"content": "hi"}, "token"),
    (ToolCallEvent, {"id": "c1", "name": "gen", "arguments": {"a": 1}, "display": "生成"}, "tool_call"),
    (ToolResultEvent, {"tool_call_id": "c1", "name": "gen", "content": "ok", "duration_ms": 5}, "tool_result"),
    (TraceEvent, {"phase": TracePhase.MODEL_REQUEST, "ts": 1.0, "payload": {"k": "v"}}, "trace"),
    (TitleUpdateEvent, {"id": "s1", "title": "夏日晚风"}, "title_update"),
    (DoneEvent, {}, "done"),
    (ErrorEvent, {"content": "炸了"}, "error"),
    (TaskPlanCreatedEvent, {"pipeline_id": "p1", "tasks": [{"id": "t1", "agent_type": "idea"}]}, "task_plan_created"),
]


def test_each_event_has_distinct_type():
    seen = set()
    for cls, kwargs, expected in _FIXTURES:
        ev = cls(**kwargs)
        assert ev.type == expected
        assert expected not in seen  # 各 type 唯一
        seen.add(expected)
    assert len(seen) == len(_FIXTURES)


def test_model_dump_json_roundtrips_via_sse_union():
    adapter = TypeAdapter(SseEvent)
    for cls, kwargs, _expected in _FIXTURES:
        ev = cls(**kwargs)
        # JSON 序列化 -> 经 discriminated union 反序列化 -> 同类同值
        rebuilt = adapter.validate_json(ev.model_dump_json())
        assert type(rebuilt) is cls
        assert rebuilt.model_dump() == ev.model_dump()


def test_required_fields_enforced():
    with pytest.raises(ValidationError):
        TokenEvent()  # 缺 content
    with pytest.raises(ValidationError):
        MessageStartEvent()  # 缺 id
    with pytest.raises(ValidationError):
        ToolCallEvent(id="c1", name="gen", display="x")  # 缺 arguments


def test_frozen_and_extra_forbidden():
    ev = TokenEvent(content="hi")
    with pytest.raises(ValidationError):
        ev.content = "mut"  # frozen
    with pytest.raises(ValidationError):
        TokenEvent(content="hi", rogue="no")  # extra forbidden


def test_task_plan_created_carries_pipeline_and_tasks():
    tasks = [{"id": "t1", "agent_type": "idea", "seq": 1, "status": "pending"}]
    ev = TaskPlanCreatedEvent(pipeline_id="p1", tasks=tasks)
    assert ev.type == "task_plan_created"
    assert ev.pipeline_id == "p1"
    assert ev.tasks == tasks
    assert ev.tasks[0]["agent_type"] == "idea"


def test_trace_event_phase_serializes_as_enum_value():
    ev = TraceEvent(phase=TracePhase.TOOL_CALL, ts=2.5, payload={})
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
