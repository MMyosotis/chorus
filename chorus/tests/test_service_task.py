"""TaskService HIL smoke test：confirm/retry/cancel + get_graph。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.session import Session
from chorus.domain.task import (
    IdeaArtifacts,
    IdeaCandidate,
    Task,
    TaskContent,
    TaskStatus,
)
from chorus.repo.connection import ConnectionFactory
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    task_repo = TaskRepository(conn)
    progress_repo = TaskProgressRepository(conn)
    content_repo = TaskContentRepository(conn)
    session_svc = SessionService(SessionRepository(conn))
    svc = TaskService(
        task_repo, TaskArtifactsRepository(conn), progress_repo, content_repo, session_svc,
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
    )
    res = svc.confirm("t1", selected=0)
    assert res["status"] == TaskStatus.FINISHED
    assert task_repo.get("t1").status == TaskStatus.FINISHED


def test_confirm_writes_terminal_updated_at():
    """确认至终态后，结束时刻写入时间戳。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "script", "awaiting_confirm", updated_at=0.0)
    svc.confirm("t1", selected=None)
    got = task_repo.get("t1")
    assert got.status == TaskStatus.FINISHED
    assert got.updated_at > 0.0


def test_retry_writes_feedback():
    """重跑翻回待执行 + 反馈写入内容表（不在调度行）。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "idea", "awaiting_confirm")
    res = svc.retry("t1", feedback="标题不够吸引")
    assert res["status"] == TaskStatus.PENDING
    got = task_repo.get("t1")
    assert got.status == TaskStatus.PENDING
    # 反馈落在内容表，不在调度行
    assert content_repo.load("t1").feedback == "标题不够吸引"


def test_retry_from_failed():
    """失败态也可重跑回 pending。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "t1", "script", "failed")
    res = svc.retry("t1", feedback="重试")
    assert res["status"] == TaskStatus.PENDING
    assert task_repo.get("t1").status == TaskStatus.PENDING


def test_cancel_pipeline():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="pending")
    _mk(task_repo, content_repo, "b", status="running")  # 运行中不可中途停
    _mk(task_repo, content_repo, "c", status="finished")
    res = svc.cancel_pipeline("s1")
    assert res["cancelled"] == 1  # 仅 pending
    assert task_repo.get("a").status == TaskStatus.CANCELLED
    assert task_repo.get("b").status == TaskStatus.RUNNING  # 运行中保留
    assert task_repo.get("c").status == TaskStatus.FINISHED


def test_cancel_no_active():
    """无 active 流水线：幂等返 cancelled=0，不报错（放弃整条对已终态流水线为 no-op）。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "c", status="finished")
    res = svc.cancel_pipeline("s1")
    assert res["cancelled"] == 0
    assert res["pipeline_id"] is None


def test_cancel_pipeline_writes_terminal_updated_at():
    """批量取消至 cancelled 后，结束时刻写入时间戳。"""
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="pending", updated_at=0.0)
    _mk(task_repo, content_repo, "b", status="running", updated_at=0.0)  # 运行中不可中途停
    _mk(task_repo, content_repo, "c", status="finished")
    svc.cancel_pipeline("s1")
    a = task_repo.get("a")
    b = task_repo.get("b")
    assert a.status == TaskStatus.CANCELLED
    assert b.status == TaskStatus.RUNNING  # 运行中保留
    assert a.updated_at > 0.0


def test_get_graph_active():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "a", status="running")
    _mk(task_repo, content_repo, "b", status="pending")
    graph = svc.get_graph("s1")
    assert graph.active is True
    assert {t.id for t in graph.nodes} == {"a", "b"}


def test_get_graph_recent_finished():
    svc, task_repo, content_repo = _setup()
    _mk(task_repo, content_repo, "old", status="finished", pipeline_id="p1", updated_at=1.0)
    _mk(task_repo, content_repo, "new", status="finished", pipeline_id="p2", updated_at=2.0)
    graph = svc.get_graph("s1")
    assert graph.active is False
    assert {t.id for t in graph.nodes} == {"new"}  # 最近 finished pipeline


def _conn_of(task_repo):
    return task_repo._conn  # noqa: SLF001 — 测试辅助


def test_get_graph_includes_progress_and_timestamps():
    """任务图每节点含时间戳与运行期进度；error 取自内容表。"""
    from chorus.services.session import SessionService as _SS
    from chorus.repo.session import SessionRepository as _SR
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    content_repo = TaskContentRepository(conn)
    svc = TaskService(task_repo, art_repo, TaskProgressRepository(conn), content_repo, _SS(_SR(conn)))
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="image",
        status="running", dependencies=[],
        created_at=0.0, updated_at=10.0,
    ))
    content_repo.insert(TaskContent(task_id="t1", invoke_message="x", progress_total=3))
    progress_repo = TaskProgressRepository(conn)
    progress_repo.set_composing("t1", 120, 2)
    progress_repo.set_composing_label("t1", "张")
    graph = svc.get_graph("s1")
    t = graph.nodes[0]
    assert t.updated_at == 10.0
    assert t.progress is not None
    assert t.progress.composing_chars == 120
    assert t.progress.composing_units == 2
    assert t.progress.composing_label == "张"
    # 配图分母（共 N 张）随内容行透进节点
    assert t.progress_total == 3
    # error 取自内容表（此处未写 → None）
    assert t.error is None


def test_get_graph_error_from_content():
    """任务图的 error 取自内容表，不在调度行。"""
    from chorus.services.session import SessionService as _SS
    from chorus.repo.session import SessionRepository as _SR
    conn = fresh_conn()
    seed_session(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    content_repo = TaskContentRepository(conn)
    svc = TaskService(task_repo, art_repo, TaskProgressRepository(conn), content_repo, _SS(_SR(conn)))
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", dependencies=[], created_at=0.0, updated_at=1.0,
    ))
    content_repo.insert(TaskContent(task_id="t1", invoke_message="x", error="boom"))
    graph = svc.get_graph("s1")
    assert graph.nodes[0].error == "boom"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
