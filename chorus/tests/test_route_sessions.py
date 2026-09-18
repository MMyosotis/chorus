"""sessions 路由 HTTP 适配测试：resume 端点的门禁映射。

只断言适配行为（会话不存在→404 / 无未回执建图挂起→409），不测续跑业务；最小 app + 依赖注入 fake service，不起 lifespan。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.routes.providers import (
    provide_intent_state_service,
    provide_session_service,
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


def _client(session: FakeSessionService, supervisor: FakeSupervisorService) -> TestClient:
    app = FastAPI()
    app.include_router(sessions_router)
    # 门禁拦截路径不触达意图与工具，占位即可
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_intent_state_service] = lambda: None
    app.dependency_overrides[provide_supervisor_service] = lambda: supervisor
    app.dependency_overrides[provide_tool_dispatch] = lambda: None
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


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
