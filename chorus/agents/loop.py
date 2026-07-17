"""agent loop 共享内核：最小回合自动机。

主调度与子 agent 共用的回合状态机步骤与工具派发，业务差异由各自策略实现。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generator, Iterable, Iterator, Optional, Protocol

import uuid6

from chorus.agents.runtime import AgentContext
from chorus.config import MODEL_CALL_TIMEOUT
from chorus.domain.events import SseEvent, ToolCallEvent, ToolResultEvent
from chorus.domain.log import ctx_fields, get_logger
from chorus.domain.stream import StreamResult, parse_tool_arguments
from chorus.hooks import HookRegistry
from chorus.tools import ToolCall, ToolContext, ToolDispatch

_logger = get_logger("loop")


class LoopSignal(Enum):
    CONTINUE = "continue"
    FINISH = "finish"


@dataclass
class LoopAction:
    """策略对单轮结局的判定：信号与附带事件。事件只被内核消费一次，推荐返回列表或元组。"""

    signal: LoopSignal
    events: Iterable[SseEvent] = ()


class LoopStrategy(Protocol):
    """agent loop 的业务差异面，内核据此驱动回合自动机，按固定顺序调用各阶段回调。"""

    max_steps: Optional[int]

    def before_turn(self) -> bool: ...
    def message_start(self, ctx: AgentContext) -> Iterable[SseEvent]: ...
    def provider_messages(self) -> list[dict]: ...
    def consume(self, stream) -> Generator[SseEvent, None, StreamResult]: ...
    def before_dispatch(self, call: ToolCall) -> None: ...
    def after_dispatch(self, call: ToolCall, dispatch: object) -> None: ...
    def after_tools(self, ctx: AgentContext, result: StreamResult,
                    pairs: list) -> LoopAction: ...
    def after_text(self, ctx: AgentContext, result: StreamResult) -> LoopAction: ...
    def on_exhausted(self) -> LoopAction: ...
    def on_error(self, ctx: AgentContext, error: BaseException) -> LoopAction: ...


class AgentLoop:
    """agent loop 共享内核：最小回合自动机，零业务分支。"""

    def __init__(self, hooks: HookRegistry, dispatcher: ToolDispatch, max_tokens: int) -> None:
        self._hooks = hooks
        self._dispatcher = dispatcher
        self._max_tokens = max_tokens

    def run(self, ctx: AgentContext, *, entry, strategy: LoopStrategy) -> Iterator[SseEvent]:
        """驱动最小回合自动机。"""
        try:
            while strategy.max_steps is None or ctx.step < strategy.max_steps:
                ctx.step += 1
                if (yield from self._run_turn(ctx, entry, strategy)) is LoopSignal.FINISH:
                    return
            yield from strategy.on_exhausted().events
        except Exception as e:
            _logger.exception("agent loop failed", extra=ctx_fields(ctx))
            ctx.outcome.exception = e
            yield from strategy.on_error(ctx, e).events

    def _run_turn(
        self, ctx: AgentContext, entry, strategy: LoopStrategy,
    ) -> Generator[SseEvent, None, LoopSignal]:
        """驱动单个回合。"""
        if not strategy.before_turn():
            return LoopSignal.FINISH
        ctx.turn.reset(message_id=str(uuid6.uuid7()))
        yield from strategy.message_start(ctx)

        ctx.turn.provider_messages = strategy.provider_messages()

        yield from self._hooks.trigger("BeforeModelRequest", ctx)
        stream = entry.client.chat.completions.create(
            model=entry.model_id, messages=ctx.turn.provider_messages,
            tools=ctx.tool_schemas or None,
            max_tokens=self._max_tokens, stream=True, timeout=MODEL_CALL_TIMEOUT,
        )
        result = yield from strategy.consume(stream)
        ctx.turn.apply_stream(result)
        yield from self._hooks.trigger("AfterModelResponse", ctx)

        if result.tool_calls:
            pairs = yield from self._dispatch_tool_calls(
                ctx, result.tool_calls, strategy=strategy,
            )
            action = strategy.after_tools(ctx, result, pairs)
        else:
            action = strategy.after_text(ctx, result)

        yield from action.events
        return action.signal

    def _dispatch_tool_calls(
        self, ctx: AgentContext, tool_calls: dict, *, strategy: LoopStrategy,
    ) -> Generator[SseEvent, None, list]:
        """按序执行工具，发钩子与气泡工具事件。"""
        tool_ctx = ToolContext(session_id=ctx.session_id)
        pairs = []
        for _, tc in sorted(tool_calls.items()):
            call = ToolCall(id=tc.id, name=tc.name, arguments=parse_tool_arguments(tc.arguments))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}

            list(self._hooks.trigger("PreToolUse", ctx, call_view))

            strategy.before_dispatch(call)
            yield ToolCallEvent(
                id=call.id, name=call.name, arguments=call.arguments,
                display=self._dispatcher.format_display(call.name, call.arguments),
                running_label=self._dispatcher.running_label(call.name),
            )
            result = self._dispatcher.dispatch(call, tool_ctx)
            strategy.after_dispatch(call, result)
            yield ToolResultEvent(
                tool_call_id=call.id, name=call.name,
                content=result.outcome.content, duration_ms=result.duration_ms,
            )
            list(self._hooks.trigger("PostToolUse", ctx, call_view, result))
            pairs.append((call, result))
        return pairs
