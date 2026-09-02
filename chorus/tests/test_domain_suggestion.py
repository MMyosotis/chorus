"""输入建议领域规则断言：近期对话筛选 / 提示词拼装 / 输出解析 / 生成服务降级。

生成服务用假客户端锚定"成功走解析、失败返空列表"两条路径，不依赖真实模型。
"""
from __future__ import annotations

from types import SimpleNamespace

from chorus.domain.intent import IntentState
from chorus.domain.message import AssistantMessage, UserMessage
from chorus.domain.suggestion import (
    SuggestionGenerationService,
    build_suggestion_prompt,
    parse_suggestions,
)


def _user(text):
    return UserMessage.transient("s1", content=text)


def _assistant(text):
    return AssistantMessage.transient("s1", content=text)


def _state(**fields):
    base = {"session_id": "s1", "image_count": 0}
    base.update(fields)
    return IntentState(**base)


def test_build_prompt_contains_intent_and_history():
    state = _state(topic="城市骑行", intent_status="capturing")
    prompt = build_suggestion_prompt(state, [_user("想做骑行图文")])
    assert "<current_intent_state>" in prompt
    assert "城市骑行" in prompt
    assert '"intent_status": "capturing"' in prompt
    assert "用户：想做骑行图文" in prompt


def test_build_prompt_empty_history_uses_placeholder():
    prompt = build_suggestion_prompt(_state(), [])
    assert "还没有对话" in prompt


def test_parse_takes_items_and_truncates_to_cap():
    raw = '{"suggestions": [' + ",".join(
        f'{{"title":"建议{i}","content":"完整内容{i}"}}' for i in range(1, 5)
    ) + ']}'
    assert [item.model_dump() for item in parse_suggestions(raw)] == [
        {"title": "建议1", "content": "完整内容1"},
        {"title": "建议2", "content": "完整内容2"},
        {"title": "建议3", "content": "完整内容3"},
    ]


def test_parse_rejects_an_invalid_group_or_non_json():
    raw = '{"suggestions":[{"title":"有效建议","content":"完整内容"},{"title":"","content":"缺标题"}]}'
    assert parse_suggestions(raw) == []
    assert parse_suggestions("不是 JSON") == []
    assert parse_suggestions('{"suggestions":[{"title":"缺内容","content":""}]}') == []


def _fake_client(content=None, error=None):
    def create(**_kwargs):
        if error is not None:
            raise error
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_generate_parses_model_output():
    service = SuggestionGenerationService(
        _fake_client(content='{"suggestions":[{"title":"选题 A","content":"请做选题 A"},{"title":"选题 B","content":"请做选题 B"},{"title":"选题 C","content":"请做选题 C"}]}'),
        "m",
    )
    result = service.generate(_state(), [_user("想写点东西")])
    assert [item.model_dump() for item in result] == [
        {"title": "选题 A", "content": "请做选题 A"},
        {"title": "选题 B", "content": "请做选题 B"},
        {"title": "选题 C", "content": "请做选题 C"},
    ]


def test_generate_returns_empty_on_failure():
    service = SuggestionGenerationService(_fake_client(error=RuntimeError("boom")), "m")
    assert service.generate(_state(), []) == []


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
