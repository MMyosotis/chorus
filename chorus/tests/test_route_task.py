"""task 路由 HTTP 适配层测试：5 端点的状态码映射。

只断言适配行为（会话不存在→404 / 参数越界→422），不测业务逻辑；最小 app + 依赖注入 fake service，不起 lifespan。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.routes.providers import provide_session_service, provide_task_service
from chorus.routes.task import router as task_router


class FakeSessionService:
    """路由仅用到会话存在性判断。"""

    def __init__(self, known: set[str]):
        self._known = set(known)

    def exists(self, session_id: str) -> bool:
        return session_id in self._known


class FakeTaskService:
    """脚本化 stub：按方法与键查表，命中返回值；存的是异常则抛出。

    未注册的调用默认抛 KeyError（对应路由 500）。11 个用例共用同一份 fake，靠键区分各用例的预期副作用。
    """

    def __init__(self):
        self._effects: dict[tuple[str, str], object] = {}

    def set(self, method: str, key: str, result) -> None:
        self._effects[(method, key)] = result

    def _call(self, method: str, key: str):
        val = self._effects.get((method, key), KeyError(key))
        if isinstance(val, Exception):
            raise val
        return val

    def get_graph(self, session_id):
        return self._call("get_graph", session_id)

    def get_activities(self, task_id, *, limit=50):
        return self._call("get_activities", task_id)

    def confirm(self, task_id, selected):
        return self._call("confirm", task_id)

    def retry(self, task_id, feedback):
        return self._call("retry", task_id)

    def cancel_pipeline(self, session_id):
        return self._call("cancel_pipeline", session_id)


def _client(session: FakeSessionService, task: FakeTaskService) -> TestClient:
    app = FastAPI()
    app.include_router(task_router)
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_task_service] = lambda: task
    return TestClient(app)


def test_get_tasks_session_not_found():
    """会话不存在 → 404，不触达任务 service。"""
    session = FakeSessionService(known=set())
    task = FakeTaskService()
    r = _client(session, task).get("/api/tasks", params={"session_id": "unknown"})
    assert r.status_code == 404


def test_get_tasks_ok():
    """会话存在 → 200 + 任务图序列化透出。"""
    from chorus.domain.task import TaskGraph, build_task_graph

    session = FakeSessionService(known={"s1"})
    task = FakeTaskService()
    task.set("get_graph", "s1", build_task_graph("p1", [], {}, {}, {}, True))
    r = _client(session, task).get("/api/tasks", params={"session_id": "s1"})
    assert r.status_code == 200
    assert r.json() == {"pipeline_id": "p1", "active": True, "tasks": []}


def test_confirm_ok():
    """正常 → 200 + 透出 service 返回体。"""
    task = FakeTaskService()
    task.set("confirm", "t1", {"id": "t1", "status": "finished"})
    r = _client(FakeSessionService({"s1"}), task).post("/api/tasks/t1/confirm", json={"selected": 0})
    assert r.status_code == 200
    assert r.json()["status"] == "finished"


def test_retry_ok():
    """正常 → 200。"""
    task = FakeTaskService()
    task.set("retry", "t1", {"id": "t1", "status": "pending"})
    r = _client(FakeSessionService({"s1"}), task).post(
        "/api/tasks/t1/retry", json={"feedback": {"note": "改标题"}}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_cancel_pipeline_session_not_found():
    """会话不存在 → 404（先于任务 service）。"""
    r = _client(FakeSessionService(set()), FakeTaskService()).post(
        "/api/sessions/unknown/pipeline:cancel"
    )
    assert r.status_code == 404


def test_cancel_pipeline_ok():
    """正常 → 200 + 透出流水线与取消数（无 active 时为 0 幂等）。"""
    task = FakeTaskService()
    task.set("cancel_pipeline", "s1", {"pipeline_id": "p1", "cancelled": 2})
    r = _client(FakeSessionService({"s1"}), task).post("/api/sessions/s1/pipeline:cancel")
    assert r.status_code == 200
    assert r.json() == {"pipeline_id": "p1", "cancelled": 2}


def test_get_activities_ok():
    task = FakeTaskService()
    task.set("get_activities", "t1", [{"id": "x1", "event_type": "started"}])
    r = _client(FakeSessionService({"s1"}), task).get("/api/tasks/t1/activities", params={"limit": 10})
    assert r.status_code == 200
    assert r.json() == {"task_id": "t1", "activities": [{"id": "x1", "event_type": "started"}]}


def test_get_activities_limit_out_of_range():
    r = _client(FakeSessionService({"s1"}), FakeTaskService()).get(
        "/api/tasks/t1/activities", params={"limit": 0})
    assert r.status_code == 422


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
