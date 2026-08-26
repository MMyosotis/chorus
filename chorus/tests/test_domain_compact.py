"""压缩纯函数测试：token 估算、超长判定、微压缩换占位、摘要指令。"""
from __future__ import annotations

from chorus.domain.compact import (
    _SUMMARY_INSTRUCTION,
    TOOL_PLACEHOLDER,
    apply_micro,
    estimate_tokens,
    is_context_overflow,
)
from chorus.domain.message import ToolMessage, UserMessage


def _user(sid: str, content: str, created_at: float = 0.0) -> UserMessage:
    return UserMessage(id=f"u-{sid}", session_id="s1", created_at=created_at, content=content)


def _tool(tid: str, content: str, created_at: float = 0.0) -> ToolMessage:
    return ToolMessage(
        id=f"t-{tid}", session_id="s1", created_at=created_at,
        tool_call_id=f"call-{tid}", name="baidu_search", content=content,
    )


def test_estimate_tokens_counts_content_and_tool_args():
    msgs = [_user("1", "a" * 100), _tool("2", "b" * 100)]
    assert estimate_tokens(msgs) == 150


def test_is_context_overflow_matches_provider_errors():
    assert is_context_overflow(Exception("This model's maximum context length is 65536 tokens"))
    assert is_context_overflow(Exception("Error code: 400 - prompt_too_long"))
    assert not is_context_overflow(Exception("connection error"))


def test_apply_micro_swaps_old_long_results_to_placeholder():
    msgs = [_tool("1", "x" * 200), _tool("2", "y" * 200), _tool("3", "z" * 200), _tool("4", "w" * 200)]
    marked, elided = apply_micro(msgs)
    # 最近三条留全文，只有滑出窗口的首条换占位；行留原位，配对键不动
    assert elided == ["t-1"]
    assert [msg.content for msg in marked] == [TOOL_PLACEHOLDER, "y" * 200, "z" * 200, "w" * 200]
    assert marked[0].id == "t-1"
    assert marked[0].tool_call_id == "call-1"


def test_apply_micro_skips_short_results():
    msgs = [_tool("1", "短"), _tool("2", "y" * 200), _tool("3", "z" * 200), _tool("4", "w" * 200)]
    assert apply_micro(msgs) == (msgs, [])


def test_apply_micro_keeps_all_when_few_tools():
    msgs = [_tool("1", "x" * 200), _tool("2", "y" * 200)]
    assert apply_micro(msgs) == (msgs, [])


def test_apply_micro_placeholder_not_reselected():
    """占位文本过短自动不再入选，重复执行不重复换行、结果稳定。"""
    msgs = [_tool("1", "x" * 200), _tool("2", "y" * 200), _tool("3", "z" * 200), _tool("4", "w" * 200)]
    once, elided = apply_micro(msgs)
    twice, elided_again = apply_micro(once)
    assert elided == ["t-1"]
    assert elided_again == []
    assert twice == once


def test_summary_instruction_avoids_memory_content():
    assert "另行注入" in _SUMMARY_INSTRUCTION
    assert "不要复述" in _SUMMARY_INSTRUCTION


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
