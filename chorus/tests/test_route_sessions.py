"""sessions 路由 HTTP 适配测试：resume 续跑门禁与会话视图端点的装配映射。

只断言适配行为（会话不存在→404 / 无未回执建图挂起→409 / 续跑判定经收集参数透传），不测视图装配业务；最小 app + 依赖注入 fake service，不起 lifespan。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.routes.providers import (
    provide_intent_state_service,
    provide_session_service,
    provide_session_view_service,
    provide_supervisor_service,
    provide_tool_dispatch,
)
from chorus.routes.sessions import router as sessions_router


class FakeSessionService:
    """路由仅用到会话存在性判断。"""

    def __init__(self, known: set[str]):
        self._known = set(known)

    def exists(self, session_id: str) -> bool:
        return session_id in self._known


class FakeSupervisorService:
    """路由仅用到收尾锁判定。"""

    def __init__(self, unreceipted: bool):
        self._unreceipted = unreceipted

    def has_unreceipted_plan(self, session_id: str) -> bool:
        return self._unreceipted


class FakeSessionViewService:
    """路由仅用到视图收集，返回固定载荷并记录调用。"""

    def __init__(self, payload: dict):
        self._payload = payload
        self.collected: list[str] = []

    def collect(self, session_id: str) -> dict:
        self.collected.append(session_id)
        return dict(self._payload)


def _client(
    session: FakeSessionService,
    supervisor: FakeSupervisorService,
    view: FakeSessionViewService | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(sessions_router)
    # 门禁拦截路径不触达意图与工具，占位即可
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_intent_state_service] = lambda: None
    app.dependency_overrides[provide_supervisor_service] = lambda: supervisor
    app.dependency_overrides[provide_tool_dispatch] = lambda: None
    app.dependency_overrides[provide_session_view_service] = lambda: view or FakeSessionViewService({})
    return TestClient(app)


def test_resume_session_not_found():
    """会话不存在 → 404。"""
    r = _client(FakeSessionService(set()), FakeSupervisorService(False)).post(
        "/api/sessions/unknown/resume"
    )
    assert r.status_code == 404


def test_resume_without_unreceipted_plan_409():
    """无未回执建图挂起（已回执或从未建图）→ 409，挡重复按铃。"""
    r = _client(FakeSessionService({"s1"}), FakeSupervisorService(False)).post(
        "/api/sessions/s1/resume"
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "no unreceipted plan to resume"


def test_session_view_not_found():
    """会话不存在 → 404，不触达视图收集。"""
    view = FakeSessionViewService({"bubbles": []})
    r = _client(FakeSessionService(set()), FakeSupervisorService(False), view).get(
        "/api/sessions/unknown/view"
    )
    assert r.status_code == 404
    assert view.collected == []


def test_session_view_returns_payload():
    """视图端点返回收集服务的装配载荷。"""
    view = FakeSessionViewService({"bubbles": [], "stage": "自由对话"})
    r = _client(FakeSessionService({"s1"}), FakeSupervisorService(True), view).get(
        "/api/sessions/s1/view"
    )
    assert r.status_code == 200
    assert r.json() == {"bubbles": [], "stage": "自由对话"}
    assert view.collected == ["s1"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
