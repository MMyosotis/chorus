# kitty/tests/test_tools_outcome.py
"""ToolOutcome 联合 + dispatch 分流契约：成功→Terminal/Reply 透传、意外异常→Reply 兜底。
运行：.venv/bin/python -m kitty.tests.test_tools_outcome
"""
from __future__ import annotations

from chorus.tools import Tool, ToolContext, ToolRegistry
from chorus.tools.framework import Reply, Terminal, DispatchResult
from chorus.tools.models import ToolCall


class _ReplyTool(Tool):
    name = "reply_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        return Reply("回传内容")


class _TerminalTool(Tool):
    name = "terminal_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        return Terminal({"plan": "x"})


class _BoomTool(Tool):
    name = "boom_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        raise RuntimeError("意外崩溃")


def _ctx():
    return ToolContext(skill_loader=None, session_id="s1")


def test_reply_dispatch_returns_reply_outcome():
    reg = ToolRegistry([_ReplyTool()])
    d = reg.dispatch(ToolCall(id="c1", name="reply_tool", arguments={}), _ctx())
    assert isinstance(d, DispatchResult)
    assert isinstance(d.outcome, Reply)
    assert d.outcome.content == "回传内容"
    assert d.tool_result.content == "回传内容"   # Reply.content 落库 + trace 共用
    assert d.tool_result.is_error is False
    assert d.tool_result.duration_ms >= 0


def test_terminal_dispatch_returns_terminal_outcome():
    reg = ToolRegistry([_TerminalTool()])
    d = reg.dispatch(ToolCall(id="c1", name="terminal_tool", arguments={}), _ctx())
    assert isinstance(d.outcome, Terminal)
    assert d.outcome.payload == {"plan": "x"}
    # Terminal 的 tool_result.content 是语义摘要——此处 Tool 未自定义，dispatch 用默认占位
    assert isinstance(d.tool_result.content, str)
    assert d.tool_result.is_error is False


def test_unexpected_exception_falls_back_to_reply():
    """run 抛意外异常 → dispatch 兜底 Reply(错误文本)，is_error=True。"""
    reg = ToolRegistry([_BoomTool()])
    d = reg.dispatch(ToolCall(id="c1", name="boom_tool", arguments={}), _ctx())
    assert isinstance(d.outcome, Reply)
    assert "意外崩溃" in d.outcome.content
    assert d.tool_result.is_error is True
    assert d.tool_result.content == d.outcome.content


def test_unknown_tool_reply():
    reg = ToolRegistry([])
    d = reg.dispatch(ToolCall(id="c1", name="ghost", arguments={}), _ctx())
    assert isinstance(d.outcome, Reply)
    assert d.tool_result.is_error is True


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
