"""task_artifacts repo 的 smoke test：upsert / load_many。

运行：``.venv/bin/python -m chorus.tests.test_repo_task_artifacts``
"""
from __future__ import annotations

from chorus.domain.task import Task
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)  # tasks 外键引用 sessions（foreign_keys=ON），须先建父行
    TaskRepository(conn).insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=0.0,
    ))
    return conn


def test_artifacts_upsert_load():
    conn = _setup()
    repo = TaskArtifactsRepository(conn)
    assert repo.load("t1") is None
    repo.upsert("t1", artifacts={"a": 1}, narrative={"done_line": "ok"})
    got = repo.load("t1")
    assert got is not None
    assert got.artifacts == {"a": 1}
    assert got.narrative["done_line"] == "ok"
    # upsert 覆盖
    repo.upsert("t1", artifacts={"a": 2}, narrative={"done_line": "new"})
    assert repo.load("t1").artifacts == {"a": 2}


def test_artifacts_load_many():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="t2", session_id="s1", pipeline_id="p1", agent_type="script",
        status="pending", invoke_message="y", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    repo.upsert("t1", {"a": 1}, {"done_line": "x"})
    repo.upsert("t2", {"b": 2}, {"done_line": "y"})
    many = repo.load_many(["t1", "t2", "t3"])
    assert set(many.keys()) == {"t1", "t2"}
    assert many["t2"].artifacts == {"b": 2}


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
