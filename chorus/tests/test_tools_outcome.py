"""ToolOutcome 联合 + dispatch 分流契约：成功→Terminal/Reply 透传、意外异常→Reply 兜底。"""
from __future__ import annotations

from chorus.tools import Tool, ToolContext, ToolDispatch
from chorus.tools.framework import Reply, Terminal, DispatchResult, ToolRunResult
from chorus.tools.models import ToolCall


def _settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


class _ReplyTool(Tool):
    name = "reply_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        return ToolRunResult(Reply("回传内容"))


class _TerminalTool(Tool):
    name = "terminal_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        return ToolRunResult(Terminal("已执行"))


class _BoomTool(Tool):
    name = "boom_tool"
    description = "d"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        raise RuntimeError("意外崩溃")


def _ctx():
    return ToolContext(session_id="s1")


def test_reply_dispatch_returns_reply_outcome():
    reg = ToolDispatch([_ReplyTool()], _settings())
    d = reg.dispatch(ToolCall(id="c1", name="reply_tool", arguments={}), _ctx())
    assert isinstance(d, DispatchResult)
    assert isinstance(d.outcome, Reply)
    assert d.outcome.content == "回传内容"   # 内容在结果上，落库与 trace 共用
    assert d.duration_ms >= 0


def test_terminal_dispatch_returns_terminal_outcome():
    reg = ToolDispatch([_TerminalTool()], _settings())
    d = reg.dispatch(ToolCall(id="c1", name="terminal_tool", arguments={}), _ctx())
    assert isinstance(d.outcome, Terminal)
    assert d.outcome.content == "已执行"


def test_unexpected_exception_falls_back_to_reply():
    """run 抛意外异常 → dispatch 兜底 Reply(错误文本)。"""
    reg = ToolDispatch([_BoomTool()], _settings())
    d = reg.dispatch(ToolCall(id="c1", name="boom_tool", arguments={}), _ctx())
    assert isinstance(d.outcome, Reply)
    assert "意外崩溃" in d.outcome.content


def test_unknown_tool_reply():
    reg = ToolDispatch([], _settings())
    d = reg.dispatch(ToolCall(id="c1", name="ghost", arguments={}), _ctx())
    assert isinstance(d.outcome, Reply)


def test_format_display_unknown_tool_does_not_raise():
    """未注册工具名返回占位文案而非抛错，保证自愈路径在求值阶段不被绕过。"""
    reg = ToolDispatch([], _settings())
    assert "ghost" in reg.format_display("ghost", {})


def test_format_display_known_tool():
    reg = ToolDispatch([_ReplyTool()], _settings())
    assert reg.format_display("reply_tool", {}) == "reply_tool"


def test_generate_image_no_unit_on_error():
    """生图失败（client 返 Error:）不计结构单元，成功才 +1。"""
    from chorus.tools.builtin.generate_image import GenerateImageTool

    class _FailClient:
        def generate(self, prompt, model_id, size):
            return "Error: 图像服务返回 HTTP 404"

    class _OkClient:
        def generate(self, prompt, model_id, size):
            return "http://img/x.png"

    class _Settings:
        def get_image_test_mode(self):
            return False

    fail_tool = GenerateImageTool(_Settings(), _stub_provider(_FailClient()))
    fail_res = fail_tool.run({"prompt": "暴雨"}, _ctx())
    assert fail_res.units_produced == 0
    assert "Error:" in fail_res.outcome.content

    ok_tool = GenerateImageTool(_Settings(), _stub_provider(_OkClient()))
    ok_res = ok_tool.run({"prompt": "暴雨"}, _ctx())
    assert ok_res.units_produced == 1
    assert ok_res.outcome.content == "http://img/x.png"


def _stub_provider(client):
    class _Entry:
        def __init__(self, inner):
            self.client = inner
            self.model_id = "m"

    class _Provider:
        def __init__(self, inner):
            self._inner = inner

        def get_entry(self):
            return _Entry(self._inner)

    return _Provider(client)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
