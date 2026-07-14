"""task_progress 表 smoke:upsert 覆盖、load、load_many。"""
from __future__ import annotations

from chorus.domain.task import Task
from chorus.domain.task.progress import TaskProgress
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _seed_task(conn, task_id="t1"):
    TaskRepository(conn).insert(Task(
        id=task_id, session_id="s1", pipeline_id="p1", agent_type="idea",
        status="pending", dependencies=[], created_at=0.0, updated_at=0.0,
    ))
    return task_id


def _repo():
    conn = fresh_conn()
    seed_session(conn)
    return TaskProgressRepository(conn), conn


def test_set_and_load():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.set_composing(tid, 100, 2)
    repo.set_composing_label(tid, "段")
    prog = repo.load(tid)
    assert prog.composing_chars == 100
    assert prog.composing_units == 2
    assert prog.composing_label == "段"


def test_set_composing_does_not_clobber_label():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.set_composing_label(tid, "段")
    repo.set_composing(tid, 100, 0)
    repo.set_composing(tid, 200, 0)
    prog = repo.load(tid)
    assert prog.composing_chars == 200
    assert prog.composing_label == "段"


def test_set_aside():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.set_aside(tid, "打算用光线挪动串起一杯咖啡的时间")
    prog = repo.load(tid)
    assert prog.aside == "打算用光线挪动串起一杯咖啡的时间"


def test_set_activity():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.set_activity(tid, "drawing", "温暖午后窗边的书桌", 1_700_000_000.0)
    repo.set_composing(tid, 30, 1)
    prog = repo.load(tid)
    assert prog.activity_kind == "drawing"
    assert prog.activity_detail == "温暖午后窗边的书桌"
    assert prog.activity_started_at == 1_700_000_000.0
    assert prog.composing_chars == 30


def test_set_activity_overwrites():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.set_activity(tid, "thinking", "", 1.0)
    repo.set_activity(tid, "composing", "", 2.0)
    prog = repo.load(tid)
    assert prog.activity_kind == "composing"
    assert prog.activity_started_at == 2.0


def test_load_missing_returns_none():
    repo, conn = _repo()
    tid = _seed_task(conn)
    assert repo.load(tid) is None


def test_load_many():
    repo, conn = _repo()
    t1 = _seed_task(conn, "t1")
    t2 = _seed_task(conn, "t2")
    repo.set_composing(t1, 10, 0)
    repo.set_composing(t2, 20, 0)
    out = repo.load_many([t1, t2, "t3"])
    assert out[t1].composing_chars == 10
    assert out[t2].composing_chars == 20
    assert "t3" not in out


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
