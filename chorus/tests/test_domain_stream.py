"""流式响应消费纯函数断言：增量累积与事件翻译。

主消费函数边发事件边回传结果；静默消费透传事件并以回调透出正文 token，供后台 agent 用。
以命名元组模拟流式分片，纯函数零外部依赖。
"""
from __future__ import annotations

import types

from chorus.domain.events import ReasoningDoneEvent, ReasoningEvent, TokenEvent
from chorus.domain.stream import StreamResult, consume_stream, silent_consume


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
    # 思考段已收尾并入结果（至少含"想想"段）
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


def test_reasoning_segment_reopens_after_mid_stream_close():
    # 中途正文触发关闭后，再开新思考段应独立计时与收尾
    stream = [
        _chunk({"reasoning_content": "想一"}, None),
        _chunk({"content": "答一"}, None),
        _chunk({"reasoning_content": "想二"}, None),
        _chunk({"content": "答二"}, "stop"),
    ]
    events, result = _run(stream)
    done_count = sum(1 for e in events if isinstance(e, ReasoningDoneEvent))
    assert done_count == 2  # 两段各自收尾
    seg_texts = [seg.text for seg in result.thinking_segments]
    assert seg_texts == ["想一", "想二"]
    assert "".join(result.text_parts) == "答一答二"


def test_tool_call_deltas_merged_by_index_no_event():
    tc1 = _Delta(index=0, id="c1", function=_Delta(name="gen", arguments='{"a":'))
    tc2 = _Delta(index=0, function=_Delta(arguments='1}'))
    stream = [_chunk({"tool_calls": [tc1]}, None), _chunk({"tool_calls": [tc2]}, "tool_calls")]
    events, result = _run(stream)
    assert events == []  # 只累积工具调用，不发工具事件
    assert set(result.tool_calls.keys()) == {0}
    merged = result.tool_calls[0]
    assert merged.id == "c1"
    assert merged.name == "gen"
    assert merged.arguments == '{"a":1}'
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


def test_silent_consume_yields_events_and_returns_result():
    stream = [_chunk({"reasoning_content": "想"}, None), _chunk({"content": "hi"}, "stop")]
    gen = silent_consume(stream)
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as si:
        result = si.value
    assert [e.type for e in events] == ["reasoning", "reasoning_done", "token"]
    assert isinstance(result, StreamResult)
    assert result.text_parts == ["hi"]
    assert result.finish_reason == "stop"
    assert len(result.thinking_segments) == 1


def test_silent_consume_on_token_callback():
    stream = [_chunk({"content": "你好"}, None), _chunk({"content": "世界"}, "stop")]
    collected = []
    gen = silent_consume(stream, on_token=lambda c: collected.append(c))
    try:
        while True:
            next(gen)
    except StopIteration as si:
        result = si.value
    assert collected == ["你好", "世界"]
    assert result.text_parts == ["你好", "世界"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
