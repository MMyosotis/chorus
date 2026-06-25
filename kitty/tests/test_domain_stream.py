# kitty/tests/test_domain_stream.py
"""流式响应消费纯函数断言：consume_stream / drain_stream 的增量累积与 SSE 事件。

覆盖 ``kitty/domain/stream.py``：把 OpenAI 流式 chunk 的增量翻译成 SSE 事件并累积
text_parts / tool_calls / thinking_segments / finish_reason。consume_stream 既 yield
事件又经生成器返回值回传 StreamResult；drain_stream 同逻辑但不 yield 事件（subagent 用）。
仅断言纯函数行为（零 IO），用 SimpleNamespace chunk 模拟 OpenAI 流式分片。

运行：``.venv/bin/python -m kitty.tests.test_domain_stream``
"""
from __future__ import annotations

import types

from kitty.domain.events import ReasoningDoneEvent, ReasoningEvent, TokenEvent
from kitty.domain.stream import StreamResult, consume_stream, drain_stream


class _Delta(types.SimpleNamespace):
    """OpenAI delta 的可空字段模拟：缺省属性返回 None（不抛 AttributeError）。"""

    def __getattr__(self, name):
        return None


def _chunk(delta_kwargs: dict, finish_reason=None):
    delta = _Delta(**delta_kwargs)
    choice = types.SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return types.SimpleNamespace(choices=[choice])


def _run(stream):
    """消费 consume_stream：收齐 yield 的事件 + 捕获生成器返回的 StreamResult。"""
    gen = consume_stream(stream)
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as si:
        return events, si.value


def test_token_deltas_yield_token_event_and_accumulate():
    stream = [_chunk({"content": "你好"}, None), _chunk({"content": "世界"}, "stop")]
    events, result = _run(stream)
    assert [e.type for e in events] == ["token", "token"]
    assert all(isinstance(e, TokenEvent) for e in events)
    assert "".join(e.content for e in events) == "你好世界"
    assert result.text_parts == ["你好", "世界"]
    assert result.finish_reason == "stop"
    assert result.thinking_segments == []
    assert result.tool_calls == {}


def test_reasoning_then_content_emits_reasoning_and_done():
    stream = [_chunk({"reasoning_content": "想想"}, None), _chunk({"content": "答"}, "stop")]
    events, result = _run(stream)
    types_seq = [e.type for e in events]
    assert types_seq[0] == "reasoning"
    assert isinstance(events[0], ReasoningEvent)
    assert events[0].content == "想想"
    assert "token" in types_seq
    assert result.text_parts == ["答"]
    # 思考段已收尾并入 thinking_segments（至少含"想想"段）
    assert any(seg.text == "想想" for seg in result.thinking_segments)
    assert any(isinstance(e, ReasoningDoneEvent) for e in events)


def test_reasoning_only_closes_at_stream_end():
    stream = [_chunk({"reasoning_content": "独白"}, "stop")]
    events, result = _run(stream)
    assert [e.type for e in events] == ["reasoning", "reasoning_done"]
    assert isinstance(events[1], ReasoningDoneEvent)
    assert len(result.thinking_segments) == 1
    assert result.thinking_segments[0].text == "独白"
    assert result.text_parts == []


def test_tool_call_deltas_merged_by_index_no_event():
    tc1 = _Delta(index=0, id="c1", function=_Delta(name="gen", arguments='{"a":'))
    tc2 = _Delta(index=0, function=_Delta(arguments='1}'))
    stream = [_chunk({"tool_calls": [tc1]}, None), _chunk({"tool_calls": [tc2]}, "tool_calls")]
    events, result = _run(stream)
    assert events == []  # consume_stream 只累积工具调用, 不 yield ToolCallEvent
    assert set(result.tool_calls.keys()) == {0}
    merged = result.tool_calls[0]
    assert merged["id"] == "c1"
    assert merged["name"] == "gen"
    assert merged["arguments"] == '{"a":1}'
    assert result.finish_reason == "tool_calls"


def test_consume_stream_returns_stream_result():
    _events, result = _run([_chunk({"content": "x"}, "stop")])
    assert isinstance(result, StreamResult)
    assert result.finish_reason == "stop"


def test_empty_stream_yields_nothing():
    events, result = _run([])
    assert events == []
    assert result.text_parts == []
    assert result.tool_calls == {}
    assert result.thinking_segments == []
    assert result.finish_reason is None


def test_drain_stream_returns_result_without_yielding():
    stream = [_chunk({"reasoning_content": "想"}, None), _chunk({"content": "hi"}, "stop")]
    result = drain_stream(stream)
    assert isinstance(result, StreamResult)
    assert result.text_parts == ["hi"]
    # drain_stream 收尾时复位 in_progress, 只产出一个思考段
    assert len(result.thinking_segments) == 1
    assert result.thinking_segments[0].text == "想"
    assert result.finish_reason == "stop"


def test_drain_stream_accumulates_tool_calls():
    tc = _Delta(index=0, id="c1", function=_Delta(name="search", arguments='{"q":"猫"}'))
    result = drain_stream([_chunk({"tool_calls": [tc]}, "tool_calls")])
    assert result.tool_calls[0]["arguments"] == '{"q":"猫"}'
    assert result.tool_calls[0]["name"] == "search"
    assert result.finish_reason == "tool_calls"
    assert result.text_parts == []


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
