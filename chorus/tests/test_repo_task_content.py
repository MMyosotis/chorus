"""TaskContentRepository smoke test：insert/load/load_many/set_error/set_feedback。"""
from __future__ import annotations

from chorus.domain.task import Task, TaskContent
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.tests._helpers import fresh_engine, seed_session


def _seed_task(engine, task_id="t1", status="pending") -> Task:
    """建 tasks 父行 + 对应 content 行，返回 Task。"""
    task = Task(
        id=task_id, session_id="s1", pipeline_id="p1", agent_type="idea",
        status=status, dependencies=[], created_at=0.0, updated_at=0.0,
    )
    TaskRepository(engine).insert(task)
    return task


def _repo():
    engine = fresh_engine()
    seed_session(engine)
    return TaskContentRepository(engine), engine


def test_insert_and_load():
    repo, engine = _repo()
    _seed_task(engine, "t1")
    repo.insert(TaskContent(task_id="t1", invoke_message="骨架：主题=测试", progress_total=3))
    got = repo.load("t1")
    assert got is not None
    assert got.invoke_message == "骨架：主题=测试"
    assert got.progress_total == 3
    assert repo.load("nope") is None


def test_load_many():
    repo, engine = _repo()
    _seed_task(engine, "t1")
    _seed_task(engine, "t2")
    repo.insert(TaskContent(task_id="t1", invoke_message="a"))
    repo.insert(TaskContent(task_id="t2", invoke_message="b"))
    m = repo.load_many(["t1", "t2", "t3"])
    assert set(m.keys()) == {"t1", "t2"}
    assert m["t1"].invoke_message == "a"
    assert repo.load_many([]) == {}


def test_set_error_upsert():
    """对已存在行更新错误信息，对不存在行 upsert 占位空串。"""
    repo, engine = _repo()
    _seed_task(engine, "t1", status="running")
    repo.insert(TaskContent(task_id="t1", invoke_message="骨架"))
    repo.set_error("t1", "boom")
    assert repo.load("t1").error == "boom"
    # 不存在行：upsert 不抛（占位空串）
    _seed_task(engine, "t2", status="running")
    repo.set_error("t2", "late")
    assert repo.load("t2").error == "late"


def test_set_feedback_upsert():
    repo, engine = _repo()
    _seed_task(engine, "t1", status="awaiting_confirm")
    repo.insert(TaskContent(task_id="t1", invoke_message="骨架"))
    repo.set_feedback("t1", "标题不够吸引")
    got = repo.load("t1")
    assert got.feedback == "标题不够吸引"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
