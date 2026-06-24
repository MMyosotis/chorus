#!/usr/bin/env python3
"""TaskRepository 的 smoke test：CAS / 哑查询 / cancel_pipeline。

运行：`.venv/bin/python -m kitty.tests.test_task_repo`
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kitty.domain.session import Session
from kitty.domain.task import Task, TaskStatus
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.session import SessionRepository
from kitty.repositories.task import TaskRepository


def _mk(task_id, status="pending", pipeline_id="p1", session_id="s1", deps=None, seq=1, **kw):
    base = dict(
        id=task_id, session_id=session_id, pipeline_id=pipeline_id,
        agent_type="idea", seq=seq, status=status, invoke_message="x",
        dependencies=deps or [], created_at=0.0, updated_at=0.0,
    )
    base.update(kw)
    return Task(**base)


def _repo():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    # tasks 外键引用 sessions（foreign_keys=ON），须先建 sessions 表并插父行
    SessionRepository(conn).insert(
        Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0)
    )
    return TaskRepository(conn), conn


def test_insert_and_get():
    repo, _ = _repo()
    repo.insert(_mk("t1"))
    got = repo.get("t1")
    assert got is not None and got.status == "pending"
    assert repo.get("nope") is None


def test_cas_update_success_and_conflict():
    repo, _ = _repo()
    repo.insert(_mk("t1", status="pending"))
    assert repo.cas_update("t1", "pending", "running") is True
    assert repo.get("t1").status == "running"
    # from_status 不匹配 → False
    assert repo.cas_update("t1", "pending", "running") is False
    # 带字段
    assert repo.cas_update("t1", "running", "failed", error="boom") is True
    assert repo.get("t1").error == "boom"


def test_cas_update_rejects_unknown_field():
    repo, _ = _repo()
    repo.insert(_mk("t1"))
    with pytest.raises(ValueError):
        repo.cas_update("t1", "pending", "running", evil="x")


def test_find_pending_with_deps():
    repo, _ = _repo()
    repo.insert(_mk("a", status="finished", deps=[]))
    repo.insert(_mk("b", status="pending", deps=["a"]))
    repo.insert(_mk("c", status="pending", deps=[]))
    result = dict((t.id, [d.id for d in deps]) for t, deps in repo.find_pending_with_deps())
    assert set(result.keys()) == {"b", "c"}
    assert result["b"] == ["a"]


def test_find_running_before():
    repo, _ = _repo()
    repo.insert(_mk("a", status="running", updated_at=10.0))
    repo.insert(_mk("b", status="running", updated_at=20.0))
    repo.insert(_mk("c", status="pending", updated_at=5.0))
    result = {t.id for t in repo.find_running_before(15.0)}
    assert result == {"a"}


def test_find_count_by_session_statuses():
    repo, conn = _repo()
    # 别的 session 的 task 不应被 s1 查到（跨 session 隔离）
    SessionRepository(conn).insert(
        Session(id="s2", title="t2", title_generated=False, created_at=0.0, updated_at=0.0)
    )
    repo.insert(_mk("a", status="pending"))
    repo.insert(_mk("b", status="running"))
    repo.insert(_mk("c", status="finished"))
    repo.insert(_mk("d", status="pending", session_id="s2", pipeline_id="p2"))
    active = {"pending", "running", "awaiting_confirm"}
    ids = {t.id for t in repo.find_by_session_statuses("s1", active)}
    assert ids == {"a", "b"}
    assert repo.count_by_session_statuses("s1", active) == 2


def test_cancel_pipeline():
    repo, _ = _repo()
    repo.insert(_mk("a", status="pending", pipeline_id="p1"))
    repo.insert(_mk("b", status="running", pipeline_id="p1"))
    repo.insert(_mk("c", status="awaiting_confirm", pipeline_id="p1"))
    repo.insert(_mk("d", status="finished", pipeline_id="p1"))  # 终态不动
    repo.insert(_mk("e", status="pending", pipeline_id="p2"))    # 别的 pipeline 不动
    n = repo.cancel_pipeline("p1")
    assert n == 3
    assert repo.get("a").status == "cancelled"
    assert repo.get("d").status == "finished"
    assert repo.get("e").status == "pending"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
