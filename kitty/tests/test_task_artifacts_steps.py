#!/usr/bin/env python3
"""task_artifacts + task_steps repo 的 smoke test。

运行：`.venv/bin/python -m kitty.tests.test_task_artifacts_steps`
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kitty.domain.session import Session
from kitty.domain.task import Task
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.session import SessionRepository
from kitty.repositories.task import TaskRepository
from kitty.repositories.task_artifacts import TaskArtifactsRepository
from kitty.repositories.task_steps import TaskStepsRepository


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    # tasks 外键引用 sessions（foreign_keys=ON），须先建 sessions 表并插父行
    SessionRepository(conn).insert(
        Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0)
    )
    TaskRepository(conn).insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea", seq=1,
        status="running", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=0.0,
    ))
    return conn


def test_artifacts_upsert_load():
    conn = _setup()
    repo = TaskArtifactsRepository(conn)
    assert repo.load("t1") is None
    repo.upsert("t1", step_output={"a": 1}, artifacts={"a": 1}, narrative={"done_line": "ok"})
    got = repo.load("t1")
    assert got is not None
    assert got.step_output == {"a": 1}
    assert got.artifacts == {"a": 1}
    assert got.narrative["done_line"] == "ok"
    # upsert 覆盖
    repo.upsert("t1", step_output={"a": 2}, artifacts={"a": 2}, narrative={"done_line": "new"})
    assert repo.load("t1").step_output == {"a": 2}


def test_artifacts_load_many():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="t2", session_id="s1", pipeline_id="p1", agent_type="script", seq=2,
        status="pending", invoke_message="y", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    repo.upsert("t1", {"a": 1}, {"a": 1}, {"done_line": "x"})
    repo.upsert("t2", {"b": 2}, {"b": 2}, {"done_line": "y"})
    many = repo.load_many(["t1", "t2", "t3"])
    assert set(many.keys()) == {"t1", "t2"}
    assert many["t2"].artifacts == {"b": 2}


def test_steps_append_list_next():
    conn = _setup()
    repo = TaskStepsRepository(conn)
    assert repo.next_iteration("t1") == 1
    repo.append("t1", iteration=1, thinking="想", text="文",
                tool_calls=[{"id": "c1", "name": "baidu_search"}],
                tool_results=[{"tool_call_id": "c1", "content": "r"}],
                finish_reason="tool_calls")
    assert repo.next_iteration("t1") == 2
    repo.append("t1", iteration=2, thinking=None, text="完成",
                tool_calls=None, tool_results=None, finish_reason="stop")
    steps = repo.list_by_task("t1")
    assert [s.iteration for s in steps] == [1, 2]
    assert steps[0].tool_calls[0]["name"] == "baidu_search"
    assert steps[1].finish_reason == "stop"


def test_steps_unique_iteration():
    conn = _setup()
    repo = TaskStepsRepository(conn)
    repo.append("t1", 1, None, None, None, None, "stop")
    with pytest.raises(Exception):  # IntegrityError
        repo.append("t1", 1, None, None, None, None, "stop")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
