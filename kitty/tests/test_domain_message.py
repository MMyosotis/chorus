# kitty/tests/test_domain_message.py
"""消息序列构造纯函数断言：build_provider_messages / build_history_view。

覆盖 ``kitty/domain/message.py``：sealed 联合（user/assistant/tool）的 to_provider_dict、
LLM 消息序列唯一构建点 ``[system] + 历史``、progress 子类型压缩、前端视图过滤 tool 并
挂回 thinking/tools。直接构造 Message 实例（纯函数, 无需 DB）。

运行：``.venv/bin/python -m kitty.tests.test_domain_message``
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from kitty.domain.message import (
    AssistantMessage,
    MessageView,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
    build_history_view,
    build_provider_messages,
)
from kitty.domain.trace import MessageTrace, ThinkingSegment, ToolInvocation


def _user(seq, content, mid="u1"):
    return UserMessage(id=mid, session_id="s", seq=seq, created_at=0.0, content=content)


def _assistant(seq, content=None, tool_calls=None, mid="a1", subtype=None):
    return AssistantMessage(
        id=mid, session_id="s", seq=seq, created_at=0.0,
        content=content, tool_calls=tool_calls or [], subtype=subtype,
    )


def _tool(seq, tool_call_id="c1", content="r", mid="t1"):
    return ToolMessage(
        id=mid, session_id="s", seq=seq, created_at=0.0,
        tool_call_id=tool_call_id, name="search", content=content,
    )


def test_build_provider_messages_prepends_system_and_preserves_order():
    msgs = [_user(1, "hi"), _assistant(2, "yo"), _tool(3)]
    out = build_provider_messages("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert [m["role"] for m in out[1:]] == ["user", "assistant", "tool"]
    # 保留传入顺序, 不按 seq 重排（传入乱序则保持乱序）
    msgs_rev = [_tool(3), _assistant(2, "yo"), _user(1, "hi")]
    out_rev = build_provider_messages("SYS", msgs_rev)
    assert [m["role"] for m in out_rev[1:]] == ["tool", "assistant", "user"]


def test_user_and_tool_provider_dict():
    assert _user(1, "hi").to_provider_dict() == {"role": "user", "content": "hi"}
    d = _tool(1, tool_call_id="c1", content="r").to_provider_dict()
    assert d == {"role": "tool", "tool_call_id": "c1", "content": "r"}


def test_assistant_tool_calls_in_provider_dict():
    tc = ToolCallSpec(id="c1", name="gen", arguments_json='{"a":1}')
    d = _assistant(1, content=None, tool_calls=[tc]).to_provider_dict()
    assert d["role"] == "assistant"
    assert d["content"] is None
    assert d["tool_calls"] == [
        {"id": "c1", "type": "function", "function": {"name": "gen", "arguments": '{"a":1}'}}
    ]


def test_assistant_progress_subtype_compressed():
    long = "这是一段很长的进度话术第一行内容\n第二行不该出现"
    d = _assistant(1, content=long, subtype="progress").to_provider_dict()
    assert d["content"].startswith("[进度] ")
    assert "第二行" not in d["content"]
    # 超过 40 字的首行被截到 40
    d2 = _assistant(2, content="啊" * 50, subtype="progress").to_provider_dict()
    assert d2["content"] == "[进度] " + "啊" * 40


def test_build_history_view_filters_tool_and_attaches_trace():
    a_id = "a1"
    msgs = [_user(1, "hi"), _assistant(2, "yo", mid=a_id), _tool(3)]
    trace_table = {
        a_id: MessageTrace(
            message_id=a_id,
            thinking=[ThinkingSegment(text="想", duration_ms=5)],
            tools=[ToolInvocation(tool_call_id="c1", name="search", arguments={},
                                  display="搜索", duration_ms=10, content="r")],
        )
    }
    views = build_history_view(msgs, lambda mid: trace_table.get(mid, MessageTrace(message_id=mid)))
    assert len(views) == 2  # tool 被过滤
    assert [v.role for v in views] == ["user", "assistant"]
    assert views[0].content == "hi"
    assert views[1].content == "yo"
    assert views[1].thinking[0].text == "想"
    assert views[1].tools[0].name == "search"


def test_build_history_view_assistant_none_content_becomes_empty():
    msgs = [_assistant(1, content=None)]
    views = build_history_view(msgs, lambda mid: MessageTrace(message_id=mid))
    assert views[0].content == ""
    assert isinstance(views[0], MessageView)


def test_build_history_view_user_has_no_trace_meta():
    msgs = [_user(1, "hi")]
    views = build_history_view(msgs, lambda mid: MessageTrace(message_id=mid))
    assert views[0].thinking == []
    assert views[0].tools == []


def test_message_frozen_and_extra_forbidden():
    u = _user(1, "hi")
    with pytest.raises(ValidationError):
        u.content = "mutate"  # frozen
    with pytest.raises(ValidationError):
        UserMessage(id="x", session_id="s", seq=1, created_at=0.0,
                    content="hi", rogue="no")  # extra forbidden


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
