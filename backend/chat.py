"""Agent loop 骨架：仅保留循环控制，所有横切逻辑通过 hooks 注入。

生命周期事件见 `backend.hooks.manager.Event`，内置 hook 见 `backend.hooks.builtin`。
新增横切能力（审计、追踪、token 计费、动态 prompt 等）只需写 hook 注册到合适事件，
无需修改本文件。
"""

from time import perf_counter
from typing import Optional

from openai import OpenAI

from backend.config import (
    API_KEY,
    BASE_URL,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
    MODEL_ID,
)
from backend.hooks import AgentContext, Event, HookManager
from backend.tools import get_tool_schemas

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 由 app 注入
_store = None
_hooks: Optional[HookManager] = None


def init_chat(store, hooks: HookManager) -> None:
    """注入 ConversationStore 和 HookManager。"""
    global _store, _hooks
    _store = store
    _hooks = hooks


def _accumulate_stream(stream):
    """消费流式响应，yield token / reasoning / reasoning_done 事件。

    返回 (text_parts, accumulated_tool_calls, finish_reason, thinking_segments)。
    thinking_segments: list[{"text": str, "duration_ms": int}]
    """
    accumulated: dict[int, dict] = {}
    text_parts: list[str] = []
    finish_reason = None

    thinking_segments: list[dict] = []
    cur_reasoning_parts: list[str] = []
    thinking_started_at: Optional[float] = None
    thinking_in_progress = False

    def _close_thinking():
        nonlocal thinking_started_at, thinking_in_progress, cur_reasoning_parts
        if not thinking_in_progress:
            return None
        duration_ms = int((perf_counter() - (thinking_started_at or perf_counter())) * 1000)
        thinking_segments.append({
            "text": "".join(cur_reasoning_parts),
            "duration_ms": duration_ms,
        })
        cur_reasoning_parts = []
        thinking_started_at = None
        thinking_in_progress = False
        return duration_ms

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta
        if choice.finish_reason is not None:
            finish_reason = choice.finish_reason

        reasoning_chunk = getattr(delta, "reasoning_content", None)
        if reasoning_chunk:
            if not thinking_in_progress:
                thinking_started_at = perf_counter()
                thinking_in_progress = True
            cur_reasoning_parts.append(reasoning_chunk)
            yield {"type": "reasoning", "content": reasoning_chunk}

        if thinking_in_progress and (delta.content or delta.tool_calls):
            duration_ms = _close_thinking()
            if duration_ms is not None:
                yield {"type": "reasoning_done", "duration_ms": duration_ms}

        if delta.content:
            text_parts.append(delta.content)
            yield {"type": "token", "content": delta.content}

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in accumulated:
                    accumulated[idx] = {"id": "", "name": "", "arguments": ""}
                entry = accumulated[idx]
                if tc_delta.id:
                    entry["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        entry["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments

    if thinking_in_progress:
        duration_ms = _close_thinking()
        if duration_ms is not None:
            yield {"type": "reasoning_done", "duration_ms": duration_ms}

    return text_parts, accumulated, finish_reason, thinking_segments


# noinspection PyTypeChecker
def chat_stream(user_message: str, conversation_id: str):
    """Hook-driven agent loop。每次 yield 一个事件 dict（SSE payload）。"""
    if _store is None or _hooks is None:
        yield {"type": "error", "content": "chat module not initialized"}
        return

    try:
        conv = _store.get(conversation_id)
    except KeyError:
        yield {"type": "error", "content": "conversation not found"}
        return

    ctx = AgentContext(
        conversation_id=conversation_id,
        user_message=user_message,
        conv=conv,
        store=_store,
        history_snapshot_len=len(conv["history"]),
        tool_schemas=get_tool_schemas(),
    )

    yield from _hooks.trigger(Event.LoopStart, ctx)

    try:
        for i in range(MAX_TOOL_ITERATIONS):
            ctx.iteration_index = i
            ctx.text_parts = None
            ctx.accumulated_tool_calls = None
            ctx.finish_reason = None
            ctx.thinking_segments = None
            ctx.provider_messages = None

            yield from _hooks.trigger(Event.IterationStart, ctx)
            yield from _hooks.trigger(Event.BeforeModelRequest, ctx)

            stream = client.chat.completions.create(
                model=MODEL_ID,
                messages=ctx.provider_messages,
                tools=ctx.tool_schemas,
                max_tokens=MAX_TOKENS,
                stream=True,
            )

            (
                ctx.text_parts,
                ctx.accumulated_tool_calls,
                ctx.finish_reason,
                ctx.thinking_segments,
            ) = yield from _accumulate_stream(stream)

            if ctx.thinking_segments and ctx.msg_meta is not None:
                ctx.msg_meta["thinking"].extend(ctx.thinking_segments)

            if ctx.finish_reason != "tool_calls" or not ctx.accumulated_tool_calls:
                yield from _hooks.trigger(Event.AssistantTextResponse, ctx)
                return

            yield from _hooks.trigger(Event.ToolCallsDetected, ctx)
            yield from _hooks.trigger(Event.IterationEnd, ctx)

        ctx.done_reason = "max_iterations_reached"
        yield from _hooks.trigger(Event.LoopEnd, ctx)

    except Exception as e:
        ctx.exception = e
        yield from _hooks.trigger(Event.LoopError, ctx)
