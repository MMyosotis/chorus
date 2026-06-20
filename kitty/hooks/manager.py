"""HookManager：8 个具名方法按字面顺序调用该事件的 hook，异常 fail-open。

每个事件方法里用代码字面顺序表达该事件的 hook 触发顺序——顺序约束（谁先谁后）写在
代码里，而非靠注册列表顺序 + 注释。单个 hook 抛错只打日志、不中断主流程。

调用方（ChatService）直接调 on_xxx(ctx)，不再经 emit(Enum, ctx) 反射分发。
"""

from __future__ import annotations

import logging
from typing import Callable, Iterable, Iterator, Optional

from kitty.domain.agent import AgentContext
from kitty.domain.events import SseEvent
from kitty.hooks.base import Hook
from kitty.hooks.builtin.trace import TraceHook
from kitty.hooks.registry import HookBundle

logger = logging.getLogger(__name__)

# hook 处理函数：普通 hook 的 handle，或 TraceHook 的某个 bound method。
HookFn = Callable[[AgentContext], Optional[Iterable[SseEvent]]]


class HookManager:
    def __init__(self, bundle: HookBundle) -> None:
        self._sys_prompt = bundle.sys_prompt
        self._iteration_start = bundle.iteration_start
        self._sanitizer = bundle.sanitizer
        self._trace = bundle.trace
        self._text_response = bundle.text_response
        self._tool_call = bundle.tool_call
        self._persistence = bundle.persistence
        self._title = bundle.title
        self._rollback = bundle.rollback

    def on_loop_start(self, ctx: AgentContext) -> Iterator[SseEvent]:
        yield from self._run(self._sys_prompt.handle, ctx)

    def on_iteration_start(self, ctx: AgentContext) -> Iterator[SseEvent]:
        yield from self._run(self._iteration_start.handle, ctx)

    def on_before_model_request(self, ctx: AgentContext) -> Iterator[SseEvent]:
        # sanitizer 先（生成 provider_messages），trace 后（读它）
        yield from self._run(self._sanitizer.handle, ctx)
        yield from self._run(self._trace.before_model_request, ctx)

    def on_assistant_text_response(self, ctx: AgentContext) -> Iterator[SseEvent]:
        # trace 先（model_response），text_response 后（append+done），title 最后
        yield from self._run(self._trace.assistant_text_response, ctx)
        yield from self._run(self._text_response.handle, ctx)
        yield from self._run(self._title.handle, ctx)

    def on_tool_calls_detected(self, ctx: AgentContext) -> Iterator[SseEvent]:
        # trace 先（model_response），tool_call 后（执行）
        yield from self._run(self._trace.tool_calls_detected, ctx)
        yield from self._run(self._tool_call.handle, ctx)

    def on_loop_end(self, ctx: AgentContext) -> Iterator[SseEvent]:
        # trace 先（loop_end），persistence 后（done）
        yield from self._run(self._trace.loop_end, ctx)
        yield from self._run(self._persistence.handle, ctx)

    def on_loop_error(self, ctx: AgentContext) -> Iterator[SseEvent]:
        yield from self._run(self._rollback.handle, ctx)

    @staticmethod
    def _run(fn: HookFn, ctx: AgentContext) -> Iterator[SseEvent]:
        try:
            result = fn(ctx)
        except Exception as e:
            logger.warning("hook %s failed: %s", getattr(fn, "__self__", fn), e)
            return
        if result is not None:
            yield from result
