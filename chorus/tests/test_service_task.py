"""TaskService HIL smoke test：confirm/retry/cancel + get_graph。

运行：.venv/bin/python -m kitty.tests.test_service_task
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chorus.domain.session import Session
from chorus.domain.task import Task, TaskStatus
from chorus.repositories.connection import ConnectionFactory
from chorus.repositories.session import SessionRepository
from chorus.repositories.task import TaskRepository
from chorus.repositories.task_artifacts import TaskArtifactsRepository
from chorus.repositories.task_steps import TaskStepsRepository
from chorus.services.task import ConflictError, TaskService


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    task_repo = TaskRepository(conn)
    return TaskService(task_repo, TaskArtifactsRepository(conn), TaskStepsRepository(conn), None), task_repo


def _mk(task_repo, tid, agent_type="idea", status="awaiting_confirm", pipeline_id="p1", seq=1, updated_at=0.0):
    task_repo.insert(Task(
        id=tid, session_id="s1", pipeline_id=pipeline_id, agent_type=agent_type, seq=seq,
        status=status, invoke_message="x", dependencies=[], created_at=0.0, updated_at=updated_at,
    ))


def test_confirm_idea_with_selected():
    svc, task_repo = _setup()
    _mk(task_repo, "t1", "idea", "awaiting_confirm")
    TaskArtifactsRepository(_conn_of(task_repo)).upsert(
        "t1", {"candidates": [{"index": 0}]}, {"candidates": [{"index": 0}]}, {"done_line": "x"})
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


def test_get_graph_active():
    svc, task_repo = _setup()
    _mk(task_repo, "a", status="running")
    _mk(task_repo, "b", status="pending", seq=2)
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


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
