"""suggestions 路由 HTTP 适配：POST /suggestions 的 404/200 映射与会话上下文透传。

只断言适配层（会话不存在 -> 404、意图与消息透传给生成服务），生成逻辑由领域测试覆盖。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.domain.intent import IntentState
from chorus.domain.message import UserMessage
from chorus.routes.providers import (
    provide_intent_state_service,
    provide_message_service,
    provide_session_service,
    provide_suggestion_service,
)
from chorus.routes.sessions import router as sessions_router


class FakeSessionService:
    def __init__(self, known):
        self._known = set(known)

    def exists(self, session_id):
        return session_id in self._known


class FakeIntentStateService:
    def get(self, session_id):
        return IntentState(session_id=session_id, topic="城市骑行", image_count=0)


class FakeMessageService:
    def __init__(self, messages):
        self._messages = messages

    def list_messages(self, session_id):
        return self._messages


class FakeSuggestionService:
    def __init__(self):
        self.calls = []

    def generate(self, state, messages):
        self.calls.append((state, messages))
        return [
            {"title": "建议一", "content": "完整建议一"},
            {"title": "建议二", "content": "完整建议二"},
            {"title": "建议三", "content": "完整建议三"},
        ]


def _client(session, intent, message, suggestion):
    app = FastAPI()
    app.include_router(sessions_router)
    app.dependency_overrides[provide_session_service] = lambda: session
    app.dependency_overrides[provide_intent_state_service] = lambda: intent
    app.dependency_overrides[provide_message_service] = lambda: message
    app.dependency_overrides[provide_suggestion_service] = lambda: suggestion
    return TestClient(app)


def test_suggest_session_not_found():
    r = _client(
        FakeSessionService(set()),
        FakeIntentStateService(),
        FakeMessageService([]),
        FakeSuggestionService(),
    ).post("/api/sessions/unknown/suggestions")
    assert r.status_code == 404


def test_suggest_returns_suggestions_with_context():
    suggestion = FakeSuggestionService()
    messages = [UserMessage.transient("s1", content="想做骑行图文")]
    r = _client(
        FakeSessionService({"s1"}),
        FakeIntentStateService(),
        FakeMessageService(messages),
        suggestion,
    ).post("/api/sessions/s1/suggestions")
    assert r.status_code == 200
    assert r.json() == {"suggestions": [
        {"title": "建议一", "content": "完整建议一"},
        {"title": "建议二", "content": "完整建议二"},
        {"title": "建议三", "content": "完整建议三"},
    ]}
    state, received = suggestion.calls[0]
    assert state.topic == "城市骑行"
    assert received == messages


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
