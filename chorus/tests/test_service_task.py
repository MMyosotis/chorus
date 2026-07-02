"""TaskService HIL smoke test：confirm/retry/cancel + get_graph。

运行：.venv/bin/python -m kitty.tests.test_service_task
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chorus.domain.session import Session
from chorus.domain.task import (
    IdeaArtifacts,
    IdeaCandidate,
    Narrative,
    Task,
    TaskContent,
    TaskStatus,
)
from chorus.repo.connection import ConnectionFactory
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.session import SessionService
from chorus.services.task import ConflictError, TaskService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    task_repo = TaskRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    content_repo = TaskContentRepository(conn)
    session_svc = SessionService(SessionRepository(conn))
    svc = TaskService(
        task_repo, TaskArtifactsRepository(conn), act_repo, content_repo, session_svc, conn,
    )
    return svc, task_repo, content_repo


def _mk(task_repo, content_repo, tid, agent_type="idea", status="awaiting_confirm", pipeline_id="p1", updated_at=0.0):
    task_repo.insert(Task(
        id=tid, session_id="s1", pipeline_id=pipeline_id, agent_type=agent_type,
        status=status, dependencies=[], created_at=0.0, updated_at=updated_at,
    ))
    content_repo.insert(TaskContent(task_id=tid, invoke_message="x"))


def test_confirm_idea_with_selected():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "idea", "awaiting_confirm")
    TaskArtifactsRepository(_conn_of(task_repo)).upsert(
        "t1", "idea",
        IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="t", angle="a", reason="r")]),
        Narrative(awaiting_line="y", done_line="x"),
    )
    res = svc.confirm("t1", selected=0)
    assert res["status"] == TaskStatus.FINISHED.value
    assert task_repo.get("t1").status == TaskStatus.FINISHED.value


def test_confirm_idea_requires_selected():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "idea", "awaiting_confirm")
    with pytest.raises(ConflictError):
        svc.confirm("t1", selected=None)


def test_confirm_wrong_status_conflict():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "idea", "pending")  # 非 awaiting_confirm
    with pytest.raises(ConflictError):
        svc.confirm("t1", selected=0)


def test_confirm_not_found():
    svc, _, _ = _setup()
    with pytest.raises(KeyError):
        svc.confirm("nope", selected=0)


def test_confirm_writes_terminal_updated_at():
    """C1: confirm awaiting_confirm→finished 后 updated_at 即结束时刻（终态时间由 updated_at 承担）。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "script", "awaiting_confirm", updated_at=0.0)
    svc.confirm("t1", selected=None)
    got = task_repo.get("t1")
    assert got.status == TaskStatus.FINISHED.value
    assert got.updated_at > 0.0


def test_retry_writes_feedback_and_cas():
    """retry 事务内 CAS 翻转 + 写 feedback 到 task_content（不在 tasks 调度行）。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "idea", "awaiting_confirm")
    res = svc.retry("t1", feedback={"note": "标题不够吸引"})
    assert res["status"] == TaskStatus.PENDING.value
    got = task_repo.get("t1")
    assert got.status == TaskStatus.PENDING.value
    # feedback 落在 task_content，不在调度行
    assert content_repo.load("t1").feedback == {"note": "标题不够吸引"}


def test_cancel_pipeline():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="pending")
    _mk(task_repo, content_repo, "b", status="running")
    _mk(task_repo, content_repo, "c", status="finished")
    res = svc.cancel_pipeline("s1")
    assert res["cancelled"] == 2  # a+b 非终态
    assert task_repo.get("a").status == TaskStatus.CANCELLED.value
    assert task_repo.get("c").status == TaskStatus.FINISHED.value


def test_cancel_no_active():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "c", status="finished")
    with pytest.raises(ConflictError):
        svc.cancel_pipeline("s1")


def test_cancel_pipeline_writes_terminal_updated_at():
    """C2: cancel_pipeline 批量→cancelled 后 updated_at 即结束时刻（终态时间由 updated_at 承担）。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="pending", updated_at=0.0)
    _mk(task_repo, content_repo, "b", status="running", updated_at=0.0)
    _mk(task_repo, content_repo, "c", status="finished")
    svc.cancel_pipeline("s1")
    a = task_repo.get("a")
    b = task_repo.get("b")
    assert a.status == TaskStatus.CANCELLED.value
    assert b.status == TaskStatus.CANCELLED.value
    assert a.updated_at > 0.0
    assert b.updated_at > 0.0


def test_get_graph_active():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="running")
    _mk(task_repo, content_repo, "b", status="pending")
    graph = svc.get_graph("s1")
    assert graph["active"] is True
    assert {t["id"] for t in graph["tasks"]} == {"a", "b"}


def test_get_graph_recent_finished():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "old", status="finished", pipeline_id="p1", updated_at=1.0)
    _mk(task_repo, content_repo, "new", status="finished", pipeline_id="p2", updated_at=2.0)
    graph = svc.get_graph("s1")
    assert graph["active"] is False
    assert {t["id"] for t in graph["tasks"]} == {"new"}  # 最近 finished pipeline


def _conn_of(task_repo):
    return task_repo._conn  # noqa: SLF001 — 测试辅助


def test_get_graph_includes_current_activity_and_timestamps():
    """get_graph 每个 task 含 updated_at/current_activity；error 取自 task_content。"""
    from chorus.services.session import SessionService as _SS
    from chorus.repo.session import SessionRepository as _SR
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    content_repo = TaskContentRepository(conn)
    svc = TaskService(task_repo, art_repo, act_repo, content_repo, _SS(_SR(conn)), conn)
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="image",
        status="running", dependencies=[],
        created_at=0.0, updated_at=10.0,
    ))
    content_repo.insert(TaskContent(task_id="t1", invoke_message="x", progress_total=3))
    act_repo.append("t1", "started", "出图中")
    graph = svc.get_graph("s1")
    t = graph["tasks"][0]
    assert t["updated_at"] == 10.0
    assert t["current_activity"] is not None
    assert t["current_activity"]["role_line"] == "出图中"
    assert t["current_activity"]["event_type"] == "started"
    # error 字段取自 task_content（此处未写 → None）
    assert t["error"] is None


def test_get_graph_error_from_content():
    """get_graph 的 error 字段取自 task_content，不在 tasks 调度行。"""
    from chorus.services.session import SessionService as _SS
    from chorus.repo.session import SessionRepository as _SR
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    content_repo = TaskContentRepository(conn)
    svc = TaskService(task_repo, art_repo, act_repo, content_repo, _SS(_SR(conn)), conn)
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", dependencies=[], created_at=0.0, updated_at=1.0,
    ))
    content_repo.insert(TaskContent(task_id="t1", invoke_message="x", error="boom"))
    graph = svc.get_graph("s1")
    assert graph["tasks"][0]["error"] == "boom"


def test_get_activities_returns_serialized_list():
    """get_activities 返 dict 列表（TypeAdapter 序列化），按 id 升序，payload 多态保留。"""
    from chorus.domain.task.models import SearchResultsPayload
    from chorus.services.session import SessionService as _SS
    from chorus.repo.session import SessionRepository as _SR
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    content_repo = TaskContentRepository(conn)
    svc = TaskService(task_repo, art_repo, act_repo, content_repo, _SS(_SR(conn)), conn)
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", dependencies=[], created_at=0.0, updated_at=0.0,
    ))
    content_repo.insert(TaskContent(task_id="t1", invoke_message="x"))
    act_repo.append("t1", "started", "a")
    act_repo.append("t1", "tool_done", "b", status="running", tool_name="baidu_search",
                    payload=SearchResultsPayload(total=1, bullets=[{"title": "t", "url": "u"}]))
    acts = svc.get_activities("t1")
    assert [a["role_line"] for a in acts] == ["a", "b"]
    assert acts[1]["payload"]["total"] == 1
    assert acts[1]["tool_name"] == "baidu_search"
    # TypeAdapter dump_python 产出的 dict 可 JSON 序列化
    import json as _json
    _json.dumps(acts)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
