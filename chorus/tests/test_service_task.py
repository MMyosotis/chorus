"""TaskService HIL smoke test：confirm/retry/cancel + get_graph。

运行：.venv/bin/python -m kitty.tests.test_service_task
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chorus.domain.session import Session
from chorus.domain.task import Task, TaskStatus
from chorus.repo.connection import ConnectionFactory
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.services.session import SessionService
from chorus.services.task import ConflictError, TaskService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    task_repo = TaskRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    session_svc = SessionService(SessionRepository(conn))
    svc = TaskService(
        task_repo, TaskArtifactsRepository(conn), act_repo, session_svc,
    )
    return svc, task_repo


def _mk(task_repo, tid, agent_type="idea", status="awaiting_confirm", pipeline_id="p1", updated_at=0.0):
    task_repo.insert(Task(
        id=tid, session_id="s1", pipeline_id=pipeline_id, agent_type=agent_type,
        status=status, invoke_message="x", dependencies=[], created_at=0.0, updated_at=updated_at,
    ))


def test_confirm_idea_with_selected():
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "idea", "awaiting_confirm")
    TaskArtifactsRepository(_conn_of(task_repo)).upsert(
        "t1", {"candidates": [{"index": 0}]}, {"done_line": "x"})
    res = svc.confirm("t1", selected=0)
    assert res["status"] == TaskStatus.FINISHED.value
    assert task_repo.get("t1").status == TaskStatus.FINISHED.value


def test_confirm_idea_requires_selected():
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "idea", "awaiting_confirm")
    with pytest.raises(ConflictError):
        svc.confirm("t1", selected=None)


def test_confirm_wrong_status_conflict():
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "idea", "pending")  # 非 awaiting_confirm
    with pytest.raises(ConflictError):
        svc.confirm("t1", selected=0)


def test_confirm_not_found():
    svc, _ = _setup()
    with pytest.raises(KeyError):
        svc.confirm("nope", selected=0)


def test_confirm_writes_finished_at():
    """C1: confirm awaiting_confirm→finished 写 finished_at（Global Constraint #15 终态口径）。"""
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "script", "awaiting_confirm")
    svc.confirm("t1", selected=None)
    got = task_repo.get("t1")
    assert got.status == TaskStatus.FINISHED.value
    assert got.finished_at is not None


def test_retry_writes_feedback_and_cas():
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "idea", "awaiting_confirm")
    res = svc.retry("t1", feedback={"note": "标题不够吸引"})
    assert res["status"] == TaskStatus.PENDING.value
    got = task_repo.get("t1")
    assert got.status == TaskStatus.PENDING.value
    assert got.feedback == {"note": "标题不够吸引"}


def test_cancel_pipeline():
    svc, task_repo = _setup()
    _mk(task_repo, "a", status="pending")
    _mk(task_repo, "b", status="running")
    _mk(task_repo, "c", status="finished")
    res = svc.cancel_pipeline("s1")
    assert res["cancelled"] == 2  # a+b 非终态
    assert task_repo.get("a").status == TaskStatus.CANCELLED.value
    assert task_repo.get("c").status == TaskStatus.FINISHED.value


def test_cancel_no_active():
    svc, task_repo = _setup()
    _mk(task_repo, "c", status="finished")
    with pytest.raises(ConflictError):
        svc.cancel_pipeline("s1")


def test_cancel_pipeline_writes_finished_at():
    """C2: cancel_pipeline 批量→cancelled 写 finished_at（Global Constraint #15 终态口径）。"""
    svc, task_repo = _setup()
    _mk(task_repo, "a", status="pending")
    _mk(task_repo, "b", status="running")
    _mk(task_repo, "c", status="finished")
    svc.cancel_pipeline("s1")
    a = task_repo.get("a")
    b = task_repo.get("b")
    assert a.status == TaskStatus.CANCELLED.value
    assert b.status == TaskStatus.CANCELLED.value
    assert a.finished_at is not None
    assert b.finished_at is not None


def test_get_graph_active():
    svc, task_repo = _setup()
    _mk(task_repo, "a", status="running")
    _mk(task_repo, "b", status="pending")
    graph = svc.get_graph("s1")
    assert graph["active"] is True
    assert {t["id"] for t in graph["tasks"]} == {"a", "b"}


def test_get_graph_recent_finished():
    svc, task_repo = _setup()
    _mk(task_repo, "old", status="finished", pipeline_id="p1", updated_at=1.0)
    _mk(task_repo, "new", status="finished", pipeline_id="p2", updated_at=2.0)
    graph = svc.get_graph("s1")
    assert graph["active"] is False
    assert {t["id"] for t in graph["tasks"]} == {"new"}  # 最近 finished pipeline


def _conn_of(task_repo):
    return task_repo._conn  # noqa: SLF001 — 测试辅助


def test_get_graph_includes_current_activity_and_timestamps():
    """get_graph 每个 task 含 updated_at/started_at/finished_at/current_activity。"""
    from chorus.repo.task_activities import TaskActivitiesRepository
    from chorus.domain.task import Task
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    from chorus.services.session import SessionService
    from chorus.repo.session import SessionRepository
    svc = TaskService(task_repo, art_repo, act_repo, SessionService(SessionRepository(conn)))
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="image",
        status="running", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=10.0, started_at=5.0,
        progress_total=3,
    ))
    act_repo.append("t1", "started", "出图中")
    graph = svc.get_graph("s1")
    t = graph["tasks"][0]
    assert t["started_at"] == 5.0
    assert t["updated_at"] == 10.0
    assert t["current_activity"] is not None
    assert t["current_activity"]["role_line"] == "出图中"
    assert t["current_activity"]["event_type"] == "started"


def test_get_activities_returns_serialized_list():
    """get_activities 返 dict 列表（TypeAdapter 序列化），按 seq 升序。"""
    from chorus.repo.task_activities import TaskActivitiesRepository
    from chorus.domain.task import Task
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    from chorus.services.session import SessionService
    from chorus.repo.session import SessionRepository
    svc = TaskService(task_repo, art_repo, act_repo, SessionService(SessionRepository(conn)))
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=0.0, started_at=1.0,
    ))
    act_repo.append("t1", "started", "a")
    act_repo.append("t1", "done", "b", status="done",
                    summary_json={"type": "search_results", "total": 1})
    acts = svc.get_activities("t1")
    assert [a["seq"] for a in acts] == [1, 2]
    assert acts[1]["summary_json"]["total"] == 1
    # TypeAdapter dump_python 产出的 dict 可 JSON 序列化
    import json as _json
    _json.dumps(acts)
    # after_seq 增量
    tail = svc.get_activities("t1", after_seq=1)
    assert [a["seq"] for a in tail] == [2]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
