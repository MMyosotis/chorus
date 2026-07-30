"""intent-confirmations 路由 HTTP 适配：GET /intent-confirmations 的 404/200 映射。

只断言适配层（会话不存在->404），留档序列化由 repo smoke 覆盖。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.domain.intent import IntentConfirmation, IntentConfirmationAnswer
from chorus.routes.providers import (
    provide_intent_state_service,
    provide_session_service,
)
from chorus.routes.sessions import router as sessions_router


class FakeSessionService:
    def __init__(self, known):
        self._known = set(known)

    def exists(self, session_id):
        return session_id in self._known


class FakeIntentStateService:
    def __init__(self, confirmations=None):
        self._confirmations = confirmations or []

    def list_confirmations(self, session_id):
        return self._confirmations


def _confirmation(cid="c1", status="answered"):
    confirmation = IntentConfirmation(
        confirmation_id=cid,
        session_id="s1",
        message_id="m-intent",
        topic="爆款图文",
        platform="小红书",
        format="图文笔记",
        style="活泼",
        image_count=3,
        intent_status="ready_to_confirm",
        progress_percent=80,
        status=status,
    )
    if status == "answered":
        confirmation.answer = IntentConfirmationAnswer(signal="confirm", label="确认并开始创作")
    return confirmation


def _client(session, intent):
    app = FastAPI()
    app.include_router(sessions_router)
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_intent_state_service] = lambda: intent
    return TestClient(app)


def test_list_intent_confirmations_session_not_found():
    r = _client(FakeSessionService(set()), FakeIntentStateService()).get("/api/sessions/unknown/intent-confirmations")
    assert r.status_code == 404


def test_list_intent_confirmations_includes_answered_archive():
    answered = _confirmation(status="answered")
    opened = _confirmation(cid="c2", status="open")
    r = _client(FakeSessionService({"s1"}), FakeIntentStateService([answered, opened])).get("/api/sessions/s1/intent-confirmations")
    assert r.status_code == 200
    confirmations = r.json()["confirmations"]
    assert len(confirmations) == 2
    assert confirmations[0]["status"] == "answered"
    assert confirmations[0]["answer"]["signal"] == "confirm"
    assert confirmations[1]["status"] == "open"
    assert confirmations[0]["message_id"] == "m-intent"
    assert "session_id" not in confirmations[0]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
