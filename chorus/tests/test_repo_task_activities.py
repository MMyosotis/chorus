# chorus/tests/test_repo_task_activities.py
"""TaskActivitiesRepository 的 smoke test：append/id 递增/latest/批量 latest/payload 多态。

载荷收敛为单 payload JSON 列（具名 dataclass 序列化），仿 task_artifacts.artifacts。

运行：``.venv/bin/python -m chorus.tests.test_repo_task_activities``
"""
from __future__ import annotations

from chorus.domain.task import Task
from chorus.domain.task.activity import ActivityDraft, SearchResultsPayload
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _seed_task(conn, task_id="t1"):
    """建 tasks 父行（task_activities 外键引用 tasks）。"""
    TaskRepository(conn).insert(Task(
        id=task_id, session_id="s1", pipeline_id="p1", agent_type="idea",
        status="pending", dependencies=[], created_at=0.0, updated_at=0.0,
    ))
    return task_id


def _repo():
    conn = fresh_conn()
    seed_session(conn)
    return TaskActivitiesRepository(conn), conn


def test_append_assigns_increasing_id():
    repo, conn = _repo()
    tid = _seed_task(conn)
    a1 = repo.append(tid, ActivityDraft(event_type="started", role_line="接单啦"))
    a2 = repo.append(tid, ActivityDraft(event_type="tool_done", role_line="搜完了"))
    assert a1.id != a2.id
    assert a1.id < a2.id  # 自增趋势递增
    assert a1.event_type == "started" and a1.status == "running"


def test_list_by_task_orders_by_id():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, ActivityDraft(event_type="started", role_line="a"))
    repo.append(tid, ActivityDraft(event_type="tool_done", role_line="b"))
    repo.append(tid, ActivityDraft(event_type="done", role_line="c", status="done"))
    all_rows = repo.list_by_task(tid)
    assert [r.role_line for r in all_rows] == ["a", "b", "c"]
    assert all(all_rows[i].id < all_rows[i + 1].id for i in range(len(all_rows) - 1))


def test_latest_by_task_and_latest_by_tasks():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, ActivityDraft(event_type="started", role_line="a"))
    repo.append(tid, ActivityDraft(event_type="done", role_line="b", status="done"))
    assert repo.latest_by_task(tid).role_line == "b"
    # 空 task 返 None
    assert repo.latest_by_task("nope") is None
    # 批量
    _seed_task(conn, "t2")
    repo.append("t2", ActivityDraft(event_type="started", role_line="c"))
    m = repo.latest_by_tasks(["t1", "t2", "t3"])
    assert set(m.keys()) == {"t1", "t2"}
    assert m["t1"].role_line == "b"
    assert m["t2"].role_line == "c"
    # 空列表不报错
    assert repo.latest_by_tasks([]) == {}


def test_payload_roundtrip_with_dataclass():
    """payload 收具名 dataclass，序列化/反序列化往返保持 typed 类型。"""
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, ActivityDraft(
        event_type="tool_done", role_line="搜完了", tool_name="baidu_search",
        payload=SearchResultsPayload(total=3, bullets=[{"title": "t", "url": "u"}]),
    ))
    got = repo.latest_by_task(tid)
    assert got.tool_name == "baidu_search"
    assert isinstance(got.payload, SearchResultsPayload)
    assert got.payload.total == 3
    assert got.payload.bullets[0]["title"] == "t"


def test_payload_none_when_absent():
    repo, conn = _repo()
    tid = _seed_task(conn)
    repo.append(tid, ActivityDraft(event_type="started", role_line="接单啦"))
    got = repo.latest_by_task(tid)
    assert got.payload is None
    assert got.tool_name is None


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
