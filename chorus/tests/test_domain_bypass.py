"""旁路调用器：成功/失败/轨迹失败三条路径的载荷内容与异常传播。"""
from __future__ import annotations

import types

from chorus.domain.bypass import BypassCaller, BypassScope
from chorus.domain.trace import ModelUsage, TracePhase


class FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


def _client(content="正文", usage=None, error=None):
    def create(**_kwargs):
        if error is not None:
            raise error
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(usage=usage, choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def _caller(client, cost_fn=None):
    entries = []
    caller = BypassCaller(client, "m", sink=entries.append, cost_fn=cost_fn)
    return caller, entries


_SCOPE = BypassScope("s1", task_id="t1", source="subagent")


def test_call_success_records_one_entry():
    caller, entries = _caller(_client(content=" 正文 ", usage=FakeUsage(3, 5, 8)))
    out = caller.call("提示词", 512, "title", _SCOPE)
    assert out == "正文"
    assert len(entries) == 1
    entry = entries[0]
    assert entry.session_id == "s1"
    assert entry.message_id is None
    assert entry.task_id == "t1"
    assert entry.source == "subagent"
    assert entry.phase is TracePhase.BYPASS_CALL
    payload = entry.payload
    assert payload.purpose == "title"
    assert payload.model == "m"
    assert payload.prompt == "提示词"
    assert payload.max_tokens == 512
    assert payload.content == "正文"
    assert payload.status == "success"
    assert payload.usage == ModelUsage(input_tokens=3, output_tokens=5, total_tokens=8)


def test_cost_fn_folds_usage_into_entry():
    caller, entries = _caller(_client(usage=FakeUsage(100, 100, 200)), cost_fn=lambda usage: 0.5)
    caller.call("p", 64, "summary", _SCOPE)
    assert entries[0].payload.cost_cny == 0.5


def test_call_error_records_entry_and_reraises():
    caller, entries = _caller(_client(error=RuntimeError("network")))
    try:
        caller.call("p", 64, "aside", _SCOPE)
        raise AssertionError("应当上抛")
    except RuntimeError:
        pass
    assert len(entries) == 1
    payload = entries[0].payload
    assert payload.status == "error"
    assert payload.error == "network"
    assert payload.content == ""


def test_sink_failure_does_not_break_call():
    def broken_sink(_entry):
        raise RuntimeError("db down")

    caller = BypassCaller(_client(content="结果"), "m", sink=broken_sink)
    assert caller.call("p", 64, "title", _SCOPE) == "结果"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
