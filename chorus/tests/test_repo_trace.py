"""TraceRepository 多来源扩展的 smoke test：source/task_id 写入、按 session/task 聚合。

运行：``.venv/bin/python -m kitty.tests.test_repo_trace``
"""
from __future__ import annotations

from chorus.domain.trace import TraceEntry, TracePhase
from chorus.repositories.trace import TraceRepository
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


def main():
    test_add_with_source_and_task_id()
    test_schedule_phase()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
