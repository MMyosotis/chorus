"""TaskScheduler smoke：派发 + zombie 回收 + 占槽失败跳过。"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from chorus.agents.scheduler import TaskScheduler
from chorus.domain.session import Session
from chorus.domain.task import Task, TaskStatus
from chorus.repo.connection import ConnectionFactory
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    return conn, TaskRepository(conn), TaskContentRepository(conn), TaskProgressRepository(conn)


def _mk(task_repo, tid, status="pending", deps=None, updated_at=0.0):
    task_repo.insert(Task(
        id=tid, session_id="s1", pipeline_id="p1", agent_type="idea",
        status=status, dependencies=deps or [],
        created_at=0.0, updated_at=updated_at,
    ))


def test_dispatch_pending_with_finished_deps():
    """pending + deps 全 finished → 占槽 running + 调 subagent_run。"""
    conn, task_repo, content_repo, progress_repo = _setup()
    _mk(task_repo, "dep", status="finished")
    _mk(task_repo, "t1", status="pending", deps=["dep"])
    ran = []
    sched = TaskScheduler(task_repo, lambda tid: ran.append(tid) or None,
                          _fake_session(), content_repo, progress_repo,
                          interval=0.01, zombie_timeout=999)
    sched._tick()
    time.sleep(0.05)  # 等 worker 线程跑完
    assert ran == ["t1"]
    assert task_repo.get("t1").status in (TaskStatus.RUNNING,)  # 子 agent 函数是空操作，未翻转状态


def test_blocked_by_unfinished_dep():
    """pending + dep 是 running（进行中、未完成）→ t1 不调度。"""
    conn, task_repo, content_repo, progress_repo = _setup()
    _mk(task_repo, "dep", status="running", updated_at=time.time())
    _mk(task_repo, "t1", status="pending", deps=["dep"])
    ran = []
    sched = TaskScheduler(task_repo, lambda tid: ran.append(tid), _fake_session(),
                          content_repo, progress_repo, interval=0.01, zombie_timeout=999)
    sched._tick()
    assert ran == []
    assert task_repo.get("t1").status == TaskStatus.PENDING


def test_zombie_reclaim():
    """running + 心跳超时 → 翻为失败。"""
    conn, task_repo, content_repo, progress_repo = _setup()
    _mk(task_repo, "t1", status="running", updated_at=0.0)  # 很久以前的心跳
    sched = TaskScheduler(task_repo, lambda tid: None, _fake_session(),
                          content_repo, progress_repo, interval=0.01, zombie_timeout=1)
    sched._reclaim_zombies()
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert content_repo.load("t1").error == "运行超时未响应"


def test_tick_guarded_swallows_single_tick_exception():
    """单轮 _tick 抛异常时 _tick_guarded 吞掉，不外抛（防打死调度线程）。"""
    _, task_repo, content_repo, progress_repo = _setup()
    sched = TaskScheduler(task_repo, lambda tid: None, _fake_session(),
                          content_repo, progress_repo, interval=0.01, zombie_timeout=999)

    def boom():
        raise RuntimeError("boom")
    sched._tick = boom
    sched._tick_guarded()  # 不抛即通过


def _fake_session():
    class _S:
        pass
    return _S()


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
