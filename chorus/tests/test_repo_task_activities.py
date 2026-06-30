# kitty/tests/test_repo_task_activities.py
"""TaskActivitiesRepository 的 smoke test：append/seq/latest/update/批量 latest。

运行：``.venv/bin/python -m chorus.tests.test_repo_task_activities``
"""
from __future__ import annotations

import time

import pytest

from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task import TaskRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _seed_task(conn, task_id="t1"):
    """建 tasks 父行（task_activities 外键引用 tasks）。"""
    from chorus.domain.task import Task
    TaskRepository(conn).insert(Task(
        id=task_id, session_id="s1", pipeline_id="p1", agent_type="idea",
        seq=1, status="pending", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=0.0,
    ))
    return task_id


def _repo():
    conn = fresh_conn()
    seed_session(conn)
    return TaskActivitiesRepository(conn), conn


def test_append_assigns_seq_and_id():
    repo, conn = _repo()
    tid = _seed_task(conn)
    a1 = repo.append(tid, "started", "planning", "接单啦")
    a2 = repo.append(tid, "tool_done", "researching", "搜完了")
    assert a1.seq == 1 and a2.seq == 2
    assert a1.id != a2.id
    assert a1.event_type == "started" and a1.status == "running"


def test_list_by_task_orders_by_seq_and_respects_after_seq():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, "started", "planning", "a")
    repo.append(tid, "tool_done", "researching", "b")
    repo.append(tid, "done", "summarizing", "c")
    all_rows = repo.list_by_task(tid)
    assert [r.seq for r in all_rows] == [1, 2, 3]
    tail = repo.list_by_task(tid, after_seq=1)
    assert [r.seq for r in tail] == [2, 3]


def test_latest_by_task_and_latest_by_tasks():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, "started", "planning", "a")
    repo.append(tid, "done", "summarizing", "b", status="done")
    assert repo.latest_by_task(tid).role_line == "b"
    # 空 task 返 None
    assert repo.latest_by_task("nope") is None
    # 批量
    _seed_task(conn, "t2")
    repo.append("t2", "started", "planning", "c")
    m = repo.latest_by_tasks(["t1", "t2", "t3"])
    assert set(m.keys()) == {"t1", "t2"}
    assert m["t1"].role_line == "b"
    assert m["t2"].role_line == "c"
    # 空列表不报错
    assert repo.latest_by_tasks([]) == {}


def test_update_latest_if_same_action_only_when_same_running():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, "tool_started", "researching", "搜1")
    # 同 action 且 running → update（不新增行）
    updated = repo.update_latest_if_same_action(tid, "researching", role_line="搜2")
    assert updated is not None and updated.role_line == "搜2"
    assert len(repo.list_by_task(tid)) == 1
    # 不同 action → 返 None，调用方应 append
    miss = repo.update_latest_if_same_action(tid, "writing", role_line="写")
    assert miss is None


def test_json_fields_roundtrip():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(
        tid, "tool_done", "researching", "搜完了",
        summary_json={"type": "search_results", "total": 3},
        progress_json={"type": "steps", "current": 1, "total": 3},
    )
    got = repo.latest_by_task(tid)
    assert got.summary_json["total"] == 3
    assert got.progress_json["current"] == 1


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
