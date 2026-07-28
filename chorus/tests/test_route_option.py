"""option 路由 HTTP 适配：GET /option 与 POST /option:choose 的 404/409/200 映射。

只断言适配层（会话不存在->404、无 open->409），200 SSE 续跑由集成测试覆盖。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.domain.option import OptionItem, OptionPrompt
from chorus.routes.providers import (
    provide_option_service,
    provide_session_service,
    provide_supervisor_service,
    provide_tool_dispatch,
)
from chorus.routes.sessions import router as sessions_router


class FakeSessionService:
    def __init__(self, known):
        self._known = set(known)

    def exists(self, session_id):
        return session_id in self._known


class FakeOptionService:
    def __init__(self, open_prompt=None):
        self._open = open_prompt

    def get_open(self, session_id):
        return self._open


class _NoCallSupervisor:
    def resume(self, *args, **kwargs):
        raise AssertionError("404/409 适配测试不应触达 supervisor")


class _NoCallTools:
    def get_tool(self, name):
        raise AssertionError("404/409 适配测试不应触达工具")


def _open_prompt(pid="p1"):
    return OptionPrompt(
        prompt_id=pid,
        session_id="s1",
        question="选哪个",
        options=[OptionItem(signal="0", label="A", description="d")],
        allow_custom=True,
        created_at=1.0,
        status="open",
    )


def _client(session, option):
    app = FastAPI()
    app.include_router(sessions_router)
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_option_service] = lambda: option
    app.dependency_overrides[provide_supervisor_service] = lambda: _NoCallSupervisor()
    app.dependency_overrides[provide_tool_dispatch] = lambda: _NoCallTools()
    return TestClient(app)


def test_get_option_session_not_found():
    r = _client(FakeSessionService(set()), FakeOptionService()).get("/api/sessions/unknown/option")
    assert r.status_code == 404


def test_get_option_no_open_returns_null():
    r = _client(FakeSessionService({"s1"}), FakeOptionService(None)).get("/api/sessions/s1/option")
    assert r.status_code == 200
    assert r.json() == {"prompt": None}


def test_get_option_with_open_serializes():
    r = _client(FakeSessionService({"s1"}), FakeOptionService(_open_prompt())).get("/api/sessions/s1/option")
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    assert prompt["question"] == "选哪个"
    assert prompt["allow_custom"] is True
    assert prompt["options"][0]["label"] == "A"


def test_choose_option_session_not_found():
    r = _client(FakeSessionService(set()), FakeOptionService()).post(
        "/api/sessions/unknown/option:choose",
        json={"signal": "0"},
    )
    assert r.status_code == 404


def test_choose_option_no_open_returns_409():
    r = _client(FakeSessionService({"s1"}), FakeOptionService(None)).post(
        "/api/sessions/s1/option:choose",
        json={"signal": "0"},
    )
    assert r.status_code == 409


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
