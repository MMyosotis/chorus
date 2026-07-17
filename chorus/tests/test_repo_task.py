"""TaskRepository smoke test：状态翻转 / 哑查询 / cancel_pipeline / 心跳。"""
from __future__ import annotations

from chorus.domain.task import CANCELLABLE_STATUSES, Task, TaskStatus
from chorus.repo.task import TaskRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _mk(task_id, status="pending", pipeline_id="p1", session_id="s1", deps=None, **kw):
    base = dict(
        id=task_id, session_id=session_id, pipeline_id=pipeline_id,
        agent_type="idea", status=status,
        dependencies=deps or [], created_at=0.0, updated_at=0.0,
    )
    base.update(kw)
    return Task(**base)


def _repo():
    conn = fresh_conn()
    seed_session(conn)  # 须先建 sessions 父行（外键约束）
    return TaskRepository(conn), conn


def test_insert_and_get():
    repo, _ = _repo()
    repo.insert(_mk("t1"))
    got = repo.get("t1")
    assert got is not None and got.status == "pending"
    assert repo.get("nope") is None


def test_transition_updates_status():
    repo, _ = _repo()
    repo.insert(_mk("t1", status="pending"))
    assert repo.transition("t1", "running") is True
    assert repo.get("t1").status == "running"
    # 不存在的任务返回 False
    assert repo.transition("nope", "running") is False


def test_claim_writes_owner_id():
    """占槽：设为运行中并写运行租约。"""
    repo, _ = _repo()
    repo.insert(_mk("t1", status="pending"))
    assert repo.claim("t1", 100.0) is True
    t = repo.get("t1")
    assert t.status == "running" and t.owner_id == 100.0
    # 再次占槽覆盖租约归属
    assert repo.claim("t1", 200.0) is True
    assert repo.get("t1").owner_id == 200.0
    # running -> awaiting_confirm -> finished，updated_at 自动刷新
    assert repo.transition("t1", "awaiting_confirm") is True
    assert repo.transition("t1", "finished") is True
    assert repo.get("t1").status == "finished"


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
    # 别的会话的 task 不应被查到（跨会话隔离）
    seed_session(conn, sid="s2", title="t2")
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
    repo.insert(_mk("b", status="running", pipeline_id="p1"))        # 运行中不可中途停
    repo.insert(_mk("c", status="awaiting_confirm", pipeline_id="p1"))
    repo.insert(_mk("d", status="finished", pipeline_id="p1"))  # 终态不动
    repo.insert(_mk("e", status="pending", pipeline_id="p2"))    # 别的 pipeline 不动
    n = repo.cancel_pipeline("p1", CANCELLABLE_STATUSES)
    assert n == 2  # 仅 pending + awaiting_confirm
    assert repo.get("a").status == "cancelled"
    assert repo.get("b").status == "running"  # 运行中保留
    assert repo.get("d").status == "finished"
    assert repo.get("e").status == "pending"
    # 空集合不翻转（防误调）
    assert repo.cancel_pipeline("p1", []) == 0


def test_touch_updated_at():
    repo, _ = _repo()
    repo.insert(_mk("a", status="running", updated_at=10.0))
    repo.touch_updated_at("a")
    got = repo.get("a")
    assert got.updated_at > 10.0  # 已更新为当前时间
    # 不存在的 task 静默无操作（不抛）
    repo.touch_updated_at("nope")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
