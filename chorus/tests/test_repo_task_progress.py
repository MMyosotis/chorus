"""task_progress 表 smoke:upsert 覆盖、load、load_many。"""
from __future__ import annotations

from chorus.domain.task import Task
from chorus.domain.task.progress import TaskProgress
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.tests._helpers import fresh_engine, seed_session


def _seed_task(engine, task_id="t1"):
    TaskRepository(engine).insert(Task(
        id=task_id, session_id="s1", pipeline_id="p1", agent_type="idea",
        status="pending", dependencies=[], created_at=0.0, updated_at=0.0,
    ))
    return task_id


def _repo():
    engine = fresh_engine()
    seed_session(engine)
    return TaskProgressRepository(engine), engine


def test_set_and_load():
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_composing(tid, 100, 2)
    repo.set_composing_label(tid, "段")
    prog = repo.load(tid)
    assert prog.composing_chars == 100
    assert prog.composing_units == 2
    assert prog.composing_label == "段"


def test_set_composing_does_not_clobber_label():
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_composing_label(tid, "段")
    repo.set_composing(tid, 100, 0)
    repo.set_composing(tid, 200, 0)
    prog = repo.load(tid)
    assert prog.composing_chars == 200
    assert prog.composing_label == "段"


def test_set_chars_units_independent():
    """chars 与 units 分写互不覆盖:配图逐张计数不被正文写字冲掉。"""
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_composing_units(tid, 3)
    repo.set_composing_chars(tid, 120)
    prog = repo.load(tid)
    assert prog.composing_units == 3
    assert prog.composing_chars == 120
    repo.set_composing_chars(tid, 200)
    assert repo.load(tid).composing_units == 3
    repo.set_composing_units(tid, 4)
    assert repo.load(tid).composing_chars == 200


def test_set_aside():
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_aside(tid, "打算用光线挪动串起一杯咖啡的时间")
    prog = repo.load(tid)
    assert prog.aside == "打算用光线挪动串起一杯咖啡的时间"


def test_set_activity():
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_activity(tid, "drawing", "温暖午后窗边的书桌")
    repo.set_composing(tid, 30, 1)
    prog = repo.load(tid)
    assert prog.activity_kind == "drawing"
    assert prog.activity_detail == "温暖午后窗边的书桌"
    assert prog.composing_chars == 30


def test_set_activity_overwrites():
    repo, engine = _repo()
    tid = _seed_task(engine)
    repo.set_activity(tid, "thinking")
    repo.set_activity(tid, "composing")
    prog = repo.load(tid)
    assert prog.activity_kind == "composing"


def test_load_missing_returns_none():
    repo, engine = _repo()
    tid = _seed_task(engine)
    assert repo.load(tid) is None


def test_load_many():
    repo, engine = _repo()
    t1 = _seed_task(engine, "t1")
    t2 = _seed_task(engine, "t2")
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
