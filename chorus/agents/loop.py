"""agent loop 共享内核：最小回合自动机。

抽 supervisor / subagent 共享的回合状态机步骤——准入 → reset → TurnStart →
拼消息选 schema → BeforeModelRequest → 调模型 → 消费流 → AfterModelResponse →
工具/文本分流 → 终止判定；divergent 节点（历史来源、持久化、stream 消费方式、终态写入、
activity）全部进 LoopStrategy。

bright-line：kernel 只 own 共享状态机步骤 + strategy 显式声明的稳定差异点，不允许出现
按 agent 名称 / source / 类型判断的业务分支——出现即抽象失败，降级为 ``_dispatch_tool_calls``
+ 模型调用 helper 两层。

依赖切分（对齐 ToolDispatch + ToolContext 同款）：``hooks`` / ``dispatcher`` / ``max_tokens``
进程级稳定（一份，supervisor/subagent 共享同一 ``AgentLoop`` 实例），进构造器；``ctx`` / ``entry``
/ ``strategy`` 每次调用变化，走 ``run()`` 参数——strategy 是 per-call 业务差异本身，不可进构造器。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generator, Iterable, Iterator, Optional, Protocol

import uuid6

from chorus.agents.runtime import AgentContext
from chorus.domain.events import SseEvent
from chorus.domain.stream import StreamResult, parse_tool_arguments
from chorus.hooks import HookRegistry
from chorus.tools import ToolCall, ToolContext, ToolDispatch


class LoopSignal(Enum):
    CONTINUE = "continue"
    FINISH = "finish"


@dataclass
class LoopAction:
    """strategy 对单轮结局的判定：信号 + 附带事件。

    events 只会被 kernel 消费一次；推荐返回 list/tuple，若返回 generator 不得在别处复用。
    """

    signal: LoopSignal
    events: Iterable[SseEvent] = ()


class LoopStrategy(Protocol):
    """agent loop 的业务差异面，kernel 据此驱动回合自动机。

    kernel 调用顺序：before_turn → TurnStart → provider_messages
    → tool_schemas → BeforeModelRequest → 调模型 → consume → AfterModelResponse →
    有工具则 _dispatch_tool_calls + after_tools，无工具则 after_text → 据 signal 继续/结束。
    """

    max_steps: Optional[int]

    def before_turn(self, ctx: AgentContext, step: int) -> bool: ...
    def provider_messages(self, ctx: AgentContext) -> list[dict]: ...
    def tool_schemas(self, ctx: AgentContext) -> list[dict]: ...
    def consume(self, stream) -> Generator[SseEvent, None, StreamResult]: ...
    def before_dispatch(self, call: ToolCall) -> None: ...
    def after_dispatch(self, call: ToolCall, d: object) -> None: ...
    def after_tools(self, ctx: AgentContext, result: StreamResult,
                    pairs: list) -> LoopAction: ...
    def after_text(self, ctx: AgentContext, result: StreamResult) -> LoopAction: ...
    def on_exhausted(self, ctx: AgentContext) -> LoopAction: ...
    def on_error(self, ctx: AgentContext, error: BaseException) -> LoopAction: ...


class AgentLoop:
    """agent loop 共享内核：最小回合自动机。零 agent 分支。

    ``hooks`` / ``dispatcher`` / ``max_tokens`` 进程级稳定（supervisor/subagent 共享同一实例），
    进构造器；``ctx`` / ``entry`` / ``strategy`` 每次调用变化，走 ``run()`` 参数。
    """

    def __init__(self, hooks: HookRegistry, dispatcher: ToolDispatch, max_tokens: int) -> None:
        self._hooks = hooks
        self._dispatcher = dispatcher
        self._max_tokens = max_tokens

    def run(self, ctx: AgentContext, *, entry, strategy: LoopStrategy) -> Iterator[SseEvent]:
        """驱动最小回合自动机，yield SSE 事件。零 agent 分支。"""
        step = 0
        try:
            while strategy.max_steps is None or step < strategy.max_steps:
                step += 1
                if not strategy.before_turn(ctx, step):
                    return
                ctx.turn.reset(message_id=str(uuid6.uuid7()))
                yield from self._hooks.trigger("TurnStart", ctx)

                ctx.tool_schemas = strategy.tool_schemas(ctx)
                ctx.turn.provider_messages = strategy.provider_messages(ctx)

                yield from self._hooks.trigger("BeforeModelRequest", ctx)
                stream = entry.client.chat.completions.create(
                    model=entry.model_id, messages=ctx.turn.provider_messages,
                    tools=ctx.tool_schemas or None,
                    max_tokens=self._max_tokens, stream=True,
                )
                result = yield from strategy.consume(stream)
                ctx.turn.apply_stream(result)
                yield from self._hooks.trigger("AfterModelResponse", ctx)

                if result.tool_calls:
                    pairs = self._dispatch_tool_calls(ctx, result.tool_calls, strategy=strategy)
                    action = strategy.after_tools(ctx, result, pairs)
                else:
                    action = strategy.after_text(ctx, result)
                yield from action.events
                if action.signal is LoopSignal.FINISH:
                    return
            yield from strategy.on_exhausted(ctx).events
        except Exception as e:
            ctx.outcome.exception = e
            yield from strategy.on_error(ctx, e).events

    def _dispatch_tool_calls(
        self, ctx: AgentContext, tool_calls: dict, *, strategy: LoopStrategy,
    ) -> list:
        """按序执行模型请求的工具，触发 Pre/Post hook。不判 Terminal、不写 messages/activities。

        顺序钉死（activity 顺序易被重构弄坏）：
            PreToolUse → strategy.before_dispatch → dispatch → strategy.after_dispatch → PostToolUse
        """
        tool_ctx = ToolContext(session_id=ctx.session_id)
        pairs = []
        for _, tc in sorted(tool_calls.items()):
            call = ToolCall(id=tc.id, name=tc.name, arguments=parse_tool_arguments(tc.arguments))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._dispatcher.format_display(call.name, call.arguments),
                self._dispatcher.running_label(call.name),
            ))
            strategy.before_dispatch(call)
            d = self._dispatcher.dispatch(call, tool_ctx)
            strategy.after_dispatch(call, d)
            list(self._hooks.trigger("PostToolUse", ctx, call_view, d))
            pairs.append((call, d))
        return pairs
