"""TraceRepository 多来源扩展的 smoke test：source/task_id 写入、按 session/task 聚合。

运行：``.venv/bin/python -m kitty.tests.test_repo_trace``
"""
from __future__ import annotations

from chorus.domain.trace import TraceEntry, TracePhase
from chorus.repo.trace import TraceRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)
    return conn


def test_add_with_source_and_task_id():
    conn = _setup()
    repo = TraceRepository(conn)
    # supervisor trace（默认 source）
    rid = repo.add(TraceEntry(session_id="s1", message_id="m1", phase=TracePhase.MODEL_REQUEST, ts=1.0, payload={}))
    # subagent trace
    repo.add(TraceEntry(session_id="s1", task_id="t1", source="subagent",
                        phase=TracePhase.MODEL_RESPONSE, ts=2.0, payload={}))
    # scheduler trace
    repo.add(TraceEntry(session_id="s1", task_id="t1", source="scheduler",
                        phase=TracePhase.SCHEDULE, ts=3.0, payload={"event": "dispatch"}))
    by_session = repo.list_by_session("s1")
    assert len(by_session) == 3
    sources = [e.source for e in by_session]
    assert sources == ["supervisor", "subagent", "scheduler"]
    # list_by_task
    by_task = repo.list_by_task("t1")
    assert len(by_task) == 2
    assert all(e.task_id == "t1" for e in by_task)


def test_schedule_phase():
    conn = _setup()
    repo = TraceRepository(conn)
    repo.add(TraceEntry(session_id="s1", task_id="t1", source="scheduler",
                        phase=TracePhase.SCHEDULE, ts=1.0,
                        payload={"event": "zombie_reclaim", "task_id": "t1", "detail": "x"}))
    e = repo.list_by_task("t1")[0]
    assert e.phase is TracePhase.SCHEDULE
    assert e.payload["event"] == "zombie_reclaim"


def test_batch_aggregate_groups_by_message():
    """IN 批量查多条 message 的 trace 并聚合；无 trace 的 id 不在结果中。"""
    conn = _setup()
    repo = TraceRepository(conn)
    # m1: 一段思考 + 一次工具调用 + 结果
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.MODEL_RESPONSE, ts=1.0,
                        payload={"thinking_segments": [{"text": "想", "duration_ms": 5}]}))
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.TOOL_CALL, ts=2.0,
                        payload={"id": "c1", "name": "search", "arguments": {}, "display": "搜"}))
    repo.add(TraceEntry(session_id="s1", message_id="m1",
                        phase=TracePhase.TOOL_RESULT, ts=3.0,
                        payload={"tool_call_id": "c1", "name": "search", "content": "r", "duration_ms": 10}))
    # m2: 无 trace
    out = repo.batch_aggregate(["m1", "m2"])
    assert set(out.keys()) == {"m1"}  # m2 缺失不在结果
    t = out["m1"]
    assert t.thinking[0].text == "想"
    assert t.tools[0].name == "search"
    assert t.tools[0].content == "r"
    # 空入参
    assert repo.batch_aggregate([]) == {}


def main():
    test_add_with_source_and_task_id()
    test_schedule_phase()
    test_batch_aggregate_groups_by_message()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
