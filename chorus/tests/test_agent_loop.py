"""agent loop kernel 契约：最小回合自动机的轮次推进、终止信号、工具派发顺序与异常收口。

FakeClient 模拟流式分片，spy strategy 记录调用序列，spy dispatcher 桩化工具派发，不触真实 LLM / DB / SSE。
"""
from __future__ import annotations

import types

from chorus.agents.loop import AgentLoop, LoopAction, LoopSignal
from chorus.agents.runtime import AgentContext
from chorus.domain.stream import ToolCallAccumulator, silent_consume
from chorus.hooks import HookRegistry
from chorus.tools.framework import DispatchResult, Reply


class _Delta(types.SimpleNamespace):
    """OpenAI delta 的可空字段模拟：缺省属性返回 None（不抛 AttributeError）。"""

    def __getattr__(self, name):
        return None


def _chunk(delta_kwargs: dict, finish_reason=None):
    delta = _Delta(**delta_kwargs)
    choice = types.SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return types.SimpleNamespace(choices=[choice])


class _FakeEntry:
    """同时扮演 entry 与其 client：entry.client.chat.completions.create(...) 弹出脚本一轮。"""

    def __init__(self, script):
        self._script = list(script)
        self.model_id = "fake-model"
        self.client = self
        self.calls = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        return self._script.pop(0)


class _SpyDispatcher:
    """桩化 ToolDispatch：dispatch 恒返 Reply。"""

    def dispatch(self, call, ctx):
        return DispatchResult(outcome=Reply("ok"), duration_ms=1, activity_meta=None)


class _SpyStrategy:
    """记录 kernel 调用序列的最小 strategy，信号可配置。"""

    def __init__(self, *, max_steps=None,
                 after_tools_signal=LoopSignal.CONTINUE,
                 after_text_signal=LoopSignal.FINISH):
        self.max_steps = max_steps
        self._after_tools_signal = after_tools_signal
        self._after_text_signal = after_text_signal
        self.log: list[str] = []

    def before_turn(self, ctx):
        self.log.append("before_turn"); return True

    def provider_messages(self, ctx):
        self.log.append("provider_messages"); return [{"role": "user", "content": "hi"}]

    def tool_schemas(self, ctx):
        self.log.append("tool_schemas"); return []

    def consume(self, stream):
        self.log.append("consume"); return silent_consume(stream)

    def before_dispatch(self, call):
        self.log.append("before_dispatch")

    def after_dispatch(self, call, d):
        self.log.append("after_dispatch")

    def after_tools(self, ctx, result, pairs):
        self.log.append("after_tools"); return LoopAction(self._after_tools_signal, [])

    def after_text(self, ctx, result):
        self.log.append("after_text"); return LoopAction(self._after_text_signal, [])

    def on_exhausted(self, ctx):
        self.log.append("on_exhausted"); return LoopAction(LoopSignal.FINISH, [])

    def on_error(self, ctx, error):
        self.log.append("on_error"); return LoopAction(LoopSignal.FINISH, [])


def _tool_call_chunk(name="echo"):
    tc = _Delta(index=0, id="c1", function=_Delta(name=name, arguments="{}"))
    return _chunk({"tool_calls": [tc]}, "tool_calls")


def _loop(hooks=None, dispatcher=None):
    """装配一个最小 AgentLoop（默认 spy dispatcher + 空 hooks）。"""
    return AgentLoop(hooks or HookRegistry(), dispatcher or _SpyDispatcher(), 128)


def test_kernel_continues_after_tools_then_finishes_on_text():
    # 第一轮请求工具后继续；第二轮纯文本后结束
    entry = _FakeEntry([[_tool_call_chunk()], [_chunk({"content": "done"}, "stop")]])
    ctx = AgentContext(session_id="s1")
    strategy = _SpyStrategy()
    list(_loop().run(ctx, entry=entry, strategy=strategy))
    assert entry.calls == 2
    assert strategy.log.index("after_tools") < strategy.log.index("after_text")
    assert strategy.log[-1] == "after_text"          # 结束即停


def test_max_steps_exhausts_after_n_calls():
    # 每轮工具后继续，撞步数上限走耗尽分支，不多调一次模型
    entry = _FakeEntry([[_tool_call_chunk()], [_tool_call_chunk()]])
    ctx = AgentContext(session_id="s1")
    strategy = _SpyStrategy(max_steps=2)
    list(_loop().run(ctx, entry=entry, strategy=strategy))
    assert entry.calls == 2
    assert strategy.log[-1] == "on_exhausted"


def test_kernel_routes_exception_to_on_error():
    class _BoomEntry(_FakeEntry):
        def create(self, **kwargs):
            raise RuntimeError("boom")
    ctx = AgentContext(session_id="s1")
    strategy = _SpyStrategy()
    list(_loop().run(ctx, entry=_BoomEntry([]), strategy=strategy))
    assert strategy.log[-1] == "on_error"
    assert isinstance(ctx.outcome.exception, RuntimeError)


def test_dispatch_tool_calls_orders_pre_before_dispatch_after_post():
    # 顺序：Pre → before_dispatch → dispatch → after_dispatch → Post，按 index 排序
    hooks = HookRegistry()
    order: list[str] = []
    hooks.register("PreToolUse", lambda ctx, call: order.append("Pre"))
    hooks.register("PostToolUse", lambda ctx, call, result: order.append("Post"))
    tool_calls = {
        0: ToolCallAccumulator(id="c0", name="b"),
        1: ToolCallAccumulator(id="c1", name="a"),
    }

    class _DispatchSpy:
        def before_dispatch(self, call):
            order.append(f"before:{call.name}")

        def after_dispatch(self, call, d):
            order.append(f"after:{call.name}")

    pairs = _loop(hooks=hooks)._dispatch_tool_calls(
        AgentContext(session_id="s1"), tool_calls, strategy=_DispatchSpy(),
    )
    assert [c.name for c, _ in pairs] == ["b", "a"]
    assert order == [
        "Pre", "before:b", "after:b", "Post",
        "Pre", "before:a", "after:a", "Post",
    ]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
