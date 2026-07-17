"""TraceRepository 多来源 smoke test：来源与任务写入、按会话/任务聚合、四种 phase 载荷往返。"""
from __future__ import annotations

from chorus.domain.trace import (
    ModelRequest,
    ModelResponse,
    ThinkingSegment,
    TraceEntry,
    TracePhase,
    TraceToolCall,
    TraceToolResult,
)
from chorus.repo.trace import TraceRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)
    return conn


def _request() -> ModelRequest:
    return ModelRequest(model="m", messages=[{"role": "user"}], tools=[{"name": "t"}], max_tokens=8)


def test_add_with_source_and_task_id():
    conn = _setup()
    repo = TraceRepository(conn)
    # supervisor trace（默认来源）
    repo.add(TraceEntry(session_id="s1", message_id="m1", phase=TracePhase.MODEL_REQUEST,
                        created_at=1.0, payload=_request()))
    # subagent trace
    repo.add(TraceEntry(session_id="s1", task_id="t1", source="subagent",
                        phase=TracePhase.MODEL_RESPONSE, created_at=2.0,
                        payload=ModelResponse(content="ok", finish_reason="stop")))
    by_session = repo.list_by_session("s1")
    assert len(by_session) == 2
    sources = [e.source for e in by_session]
    assert sources == ["supervisor", "subagent"]
    # 按任务查
    by_task = repo.list_by_task("t1")
    assert len(by_task) == 1
    assert all(e.task_id == "t1" for e in by_task)



def test_batch_aggregate_groups_by_message():
    """IN 批量查多条 message 的 trace 并聚合；无 trace 的 id 不在结果中。"""
    conn = _setup()
    repo = TraceRepository(conn)
    # 第一条消息：思考 + 工具调用 + 结果
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.MODEL_RESPONSE, created_at=1.0,
                        payload=ModelResponse(
                            content="", finish_reason="tool_calls",
                            thinking_segments=[ThinkingSegment(text="想", duration_ms=5)])))
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.TOOL_CALL, created_at=2.0,
                        payload=TraceToolCall(tool_call_id="c1", name="search",
                                              arguments={}, display="搜")))
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.TOOL_RESULT, created_at=3.0,
                        payload=TraceToolResult(tool_call_id="c1", name="search",
                                                content="r", duration_ms=10)))
    # 第二条消息：无 trace
    out = repo.batch_aggregate(["m1", "m2"])
    assert set(out.keys()) == {"m1"}  # 第二条消息缺失不在结果
    t = out["m1"]
    assert t.thinking[0].text == "想"
    assert t.tools[0].name == "search"
    assert t.tools[0].content == "r"
    assert t.tools[0].tool_call_id == "c1"
    # 空入参
    assert repo.batch_aggregate([]) == {}


def test_payload_round_trip_all_phases():
    """四种 phase 的 payload 入库后读回，类型与字段全保留。"""
    conn = _setup()
    repo = TraceRepository(conn)
    cases = [
        (TracePhase.MODEL_REQUEST, _request()),
        (TracePhase.MODEL_RESPONSE, ModelResponse(
            content="hi", finish_reason="stop",
            tool_calls=[], thinking_segments=[ThinkingSegment(text="t", duration_ms=1)])),
        (TracePhase.TOOL_CALL, TraceToolCall(tool_call_id="c", name="n", arguments={"a": 1},
                                             display="d", running_label="跑")),
        (TracePhase.TOOL_RESULT, TraceToolResult(tool_call_id="c", name="n",
                                                 content="r", duration_ms=7)),
    ]
    for i, (phase, payload) in enumerate(cases):
        repo.add(TraceEntry(session_id="s1", phase=phase, created_at=float(i), payload=payload))
    entries = repo.list_by_session("s1")
    assert len(entries) == len(cases)
    for (phase, expected), entry in zip(cases, entries):
        assert entry.phase is phase
        assert type(entry.payload) is type(expected)
        assert entry.payload == expected


def main():
    test_add_with_source_and_task_id()
    test_batch_aggregate_groups_by_message()
    test_payload_round_trip_all_phases()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
