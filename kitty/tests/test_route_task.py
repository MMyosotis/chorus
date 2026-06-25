# kitty/tests/test_route_task.py
"""task 资源路由 HTTP 适配层测试：5 端点的状态码映射。

覆盖 ``kitty/routes/task.py`` 的 5 个端点，只断言 HTTP 适配行为（KeyError→404 /
ConflictError→409 / session 不存在→404），不测 service 业务逻辑（那是
``test_service_task``）。

不起真实 ``create_app()``（会拉起 scheduler lifespan + 触真实 DB），改用最小 FastAPI
app 仅挂 task_router，经 ``app.dependency_overrides`` 注入 fake session/task service。
TestClient 不进 lifespan → 不起 scheduler。

运行：.venv/bin/python -m kitty.tests.test_route_task
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kitty.routes.providers import provide_session_service, provide_task_service
from kitty.routes.task import router as task_router
from kitty.services.task import ConflictError


class FakeSessionService:
    """路由仅用到 ``exists(session_id) -> bool``。"""

    def __init__(self, known: set[str]):
        self._known = set(known)

    def exists(self, session_id: str) -> bool:
        return session_id in self._known


class FakeTaskService:
    """脚本化 stub：按 (method, key) 查表，命中返回值；存的是异常则抛出。

    未注册的 (method, key) 默认抛 KeyError（对应路由 404）。冲突场景显式 set 一个
    ConflictError。这样 13 个用例共用同一份 fake，靠 set() 区分各用例的预期副作用。
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

    def get_steps(self, task_id):
        return self._call("get_steps", task_id)

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


# —— GET /api/tasks ——


def test_get_tasks_session_not_found():
    """session.exists=False → 404，不触达 task service。"""
    session = FakeSessionService(known=set())
    task = FakeTaskService()
    r = _client(session, task).get("/api/tasks", params={"session_id": "unknown"})
    assert r.status_code == 404


def test_get_tasks_ok():
    """session 存在 → 200 + get_graph 返回体原样透出。"""
    session = FakeSessionService(known={"s1"})
    task = FakeTaskService()
    task.set("get_graph", "s1", {"pipeline_id": "p1", "active": True, "tasks": []})
    r = _client(session, task).get("/api/tasks", params={"session_id": "s1"})
    assert r.status_code == 200
    assert r.json() == {"pipeline_id": "p1", "active": True, "tasks": []}


# —— GET /api/tasks/{id}/steps ——


def test_get_steps_not_found():
    """未知 task_id（fake 默认 KeyError）→ 404。"""
    r = _client(FakeSessionService({"s1"}), FakeTaskService()).get("/api/tasks/nope/steps")
    assert r.status_code == 404


def test_get_steps_ok():
    """已知 task → 200，body 包成 {"steps": [...]}。"""
    task = FakeTaskService()
    task.set("get_steps", "t1", [{"iteration": 1, "finish_reason": "stop"}])
    r = _client(FakeSessionService({"s1"}), task).get("/api/tasks/t1/steps")
    assert r.status_code == 200
    assert r.json() == {"steps": [{"iteration": 1, "finish_reason": "stop"}]}


# —— POST /api/tasks/{id}/confirm ——


def test_confirm_not_found():
    """未知 task_id → KeyError → 404。"""
    r = _client(FakeSessionService({"s1"}), FakeTaskService()).post(
        "/api/tasks/nope/confirm", json={"selected": 0}
    )
    assert r.status_code == 404


def test_confirm_conflict():
    """ConflictError → 409。"""
    task = FakeTaskService()
    task.set("confirm", "t1", ConflictError("task 状态 running 不可确认"))
    r = _client(FakeSessionService({"s1"}), task).post("/api/tasks/t1/confirm", json={"selected": 0})
    assert r.status_code == 409
    assert "不可确认" in r.json()["detail"]


def test_confirm_ok():
    """正常 → 200 + 透出 service 返回体。"""
    task = FakeTaskService()
    task.set("confirm", "t1", {"id": "t1", "status": "finished"})
    r = _client(FakeSessionService({"s1"}), task).post("/api/tasks/t1/confirm", json={"selected": 0})
    assert r.status_code == 200
    assert r.json()["status"] == "finished"


# —— POST /api/tasks/{id}/retry ——


def test_retry_not_found():
    """未知 task_id → 404。retry body 必含 feedback（RetryRequest required）。"""
    r = _client(FakeSessionService({"s1"}), FakeTaskService()).post(
        "/api/tasks/nope/retry", json={"feedback": {"note": "改标题"}}
    )
    assert r.status_code == 404


def test_retry_conflict():
    """ConflictError → 409。"""
    task = FakeTaskService()
    task.set("retry", "t1", ConflictError("task 状态 finished 不可重跑"))
    r = _client(FakeSessionService({"s1"}), task).post(
        "/api/tasks/t1/retry", json={"feedback": {"note": "改标题"}}
    )
    assert r.status_code == 409


def test_retry_ok():
    """正常 → 200。"""
    task = FakeTaskService()
    task.set("retry", "t1", {"id": "t1", "status": "pending"})
    r = _client(FakeSessionService({"s1"}), task).post(
        "/api/tasks/t1/retry", json={"feedback": {"note": "改标题"}}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


# —— POST /api/sessions/{id}/pipeline:cancel ——


def test_cancel_pipeline_session_not_found():
    """session 不存在 → 404（先于 task service）。"""
    r = _client(FakeSessionService(set()), FakeTaskService()).post(
        "/api/sessions/unknown/pipeline:cancel"
    )
    assert r.status_code == 404


def test_cancel_pipeline_conflict():
    """session 存在但无 active pipeline → ConflictError → 409。"""
    task = FakeTaskService()
    task.set("cancel_pipeline", "s1", ConflictError("该会话无进行中的创作任务"))
    r = _client(FakeSessionService({"s1"}), task).post("/api/sessions/s1/pipeline:cancel")
    assert r.status_code == 409


def test_cancel_pipeline_ok():
    """正常 → 200 + 透出 {pipeline_id, cancelled}。"""
    task = FakeTaskService()
    task.set("cancel_pipeline", "s1", {"pipeline_id": "p1", "cancelled": 2})
    r = _client(FakeSessionService({"s1"}), task).post("/api/sessions/s1/pipeline:cancel")
    assert r.status_code == 200
    assert r.json() == {"pipeline_id": "p1", "cancelled": 2}


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
