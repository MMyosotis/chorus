"""task_progress 表 smoke:upsert 覆盖、load、load_many。"""
from __future__ import annotations

from chorus.domain.task import Task
from chorus.domain.task.activity import TaskProgress
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


def test_upsert_and_load():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.upsert_progress(tid, composing_chars=100, composing_units=2, composing_label="段")
    prog = repo.load(tid)
    assert prog.composing_chars == 100
    assert prog.composing_units == 2
    assert prog.composing_label == "段"


def test_upsert_partial_update():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.upsert_progress(tid, composing_chars=100, composing_label="段")
    repo.upsert_progress(tid, composing_chars=200)
    prog = repo.load(tid)
    assert prog.composing_chars == 200
    assert prog.composing_label == "段"


def test_upsert_aside():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.upsert_progress(tid, aside="打算用光线挪动串起一杯咖啡的时间")
    prog = repo.load(tid)
    assert prog.aside == "打算用光线挪动串起一杯咖啡的时间"


def test_load_missing_returns_none():
    repo, conn = _repo()
    tid = _seed_task(conn)
    assert repo.load(tid) is None


def test_load_many():
    repo, conn = _repo()
    t1 = _seed_task(conn, "t1")
    t2 = _seed_task(conn, "t2")
    repo.upsert_progress(t1, composing_chars=10)
    repo.upsert_progress(t2, composing_chars=20)
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
