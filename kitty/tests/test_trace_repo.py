#!/usr/bin/env python3
"""TraceRepository 多来源扩展的 smoke test。

运行：`.venv/bin/python -m kitty.tests.test_trace_repo`
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from kitty.domain.trace import TraceEntry, TracePhase
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.session import SessionRepository
from kitty.repositories.trace import TraceRepository


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(_session("s1"))
    return conn


def _session(sid):
    from kitty.domain.session import Session
    return Session(id=sid, title="t", title_generated=False, created_at=0.0, updated_at=0.0)


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
