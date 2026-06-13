import json
import uuid
from time import perf_counter
from typing import Optional

from openai import OpenAI

from backend.config import (
    API_KEY,
    BASE_URL,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
    MODEL_ID,
    SYSTEM_PROMPT,
)
from backend.tools import dispatch_tool, format_tool_display, get_tool_schemas

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 全局单会话历史
_history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

# 与 _history 中 assistant 消息一一对应的元数据。
# key = message_id（每个 OpenAI 轮次 = 一条 assistant 消息 = 一个气泡）；
# assistant 消息字典上挂 _meta_message_id 反向索引。
_assistant_messages: dict[str, dict] = {}


def _build_system_prompt() -> str:
    """在基础 system prompt 后追加 skill 摘要。"""
    prompt = SYSTEM_PROMPT
    try:
        from backend.skills import get_skill_loader

        loader = get_skill_loader()
        hints = loader.format_skill_hints()
        if hints:
            prompt += "\n\n" + hints
    except RuntimeError:
        pass
    return prompt


def _ensure_system_prompt():
    """更新 _history 中的 system prompt（含最新 skill 摘要）。"""
    if _history and _history[0]["role"] == "system":
        _history[0]["content"] = _build_system_prompt()


def _sanitize_for_openai(messages: list[dict]) -> list[dict]:
    """剥离自定义 _meta_* 字段，避免发给 OpenAI 时报错。"""
    return [
        {k: v for k, v in m.items() if not k.startswith("_meta_")}
        for m in messages
    ]


def get_history() -> list[dict]:
    """返回 user/assistant 消息（不含 system/tool）。
    每条 assistant 消息附带自己的 thinking / tools 元数据，用于前端刷新后恢复状态。
    """
    result = []
    for m in _history:
        if m["role"] in ("system", "tool"):
            continue
        item = {"role": m["role"], "content": m.get("content") or ""}
        if m["role"] == "assistant":
            meta = _assistant_messages.get(m.get("_meta_message_id"))
            if meta:
                item["thinking"] = meta["thinking"]
                item["tools"] = meta["tools"]
            else:
                item["thinking"] = []
                item["tools"] = []
        result.append(item)
    return result


def reset_history():
    """重置对话历史。"""
    global _history
    _history = [{"role": "system", "content": _build_system_prompt()}]
    _assistant_messages.clear()


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

        # 一旦进入正文 / 工具调用阶段，先把思考阶段封口
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

    # 流结束兜底：思考还没收尾（异常情况）
    if thinking_in_progress:
        duration_ms = _close_thinking()
        if duration_ms is not None:
            yield {"type": "reasoning_done", "duration_ms": duration_ms}

    return text_parts, accumulated, finish_reason, thinking_segments


def _on_text_response(text_parts: list[str], message_id: str):
    """模型返回纯文本（未调用工具）：写入历史，yield done。"""
    full_text = "".join(text_parts)
    if full_text:
        _history.append({
            "role": "assistant",
            "content": full_text,
            "_meta_message_id": message_id,
        })
    yield {"type": "done"}


def _on_tool_calls(text_parts: list[str], accumulated: dict[int, dict], message_id: str):
    """模型调用了工具：写入 assistant 消息，执行工具，yield 事件。"""
    tool_calls_list = [
        {
            "id": e["id"],
            "type": "function",
            "function": {"name": e["name"], "arguments": e["arguments"]},
        }
        for _, e in sorted(accumulated.items())
    ]

    _history.append({
        "role": "assistant",
        "content": "".join(text_parts) or None,
        "tool_calls": tool_calls_list,
        "_meta_message_id": message_id,
    })

    msg_meta = _assistant_messages.setdefault(message_id, {"thinking": [], "tools": []})

    for tc in tool_calls_list:
        tool_name = tc["function"]["name"]
        try:
            tool_args = json.loads(tc["function"]["arguments"])
        except json.JSONDecodeError:
            tool_args = {}

        display = format_tool_display(tool_name, tool_args)

        yield {
            "type": "tool_call",
            "id": tc["id"],
            "name": tool_name,
            "arguments": tool_args,
            "display": display,
        }

        t0 = perf_counter()
        result = dispatch_tool(tool_name, tool_args)
        duration_ms = int((perf_counter() - t0) * 1000)

        yield {
            "type": "tool_result",
            "tool_call_id": tc["id"],
            "name": tool_name,
            "content": result,
            "duration_ms": duration_ms,
        }

        msg_meta["tools"].append({
            "name": tool_name,
            "arguments": tool_args,
            "duration_ms": duration_ms,
            "content": result,
            "display": display,
        })

        _history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})


# noinspection PyTypeChecker
def chat_stream(user_message: str):
    """流式 agent loop，支持 tool calling。每次 yield 一个事件 dict。

    每个 OpenAI 轮次 = 一条 assistant 历史消息 = 一个前端气泡，前端依据
    `message_start` 事件创建新气泡，后续 `reasoning` / `token` / `tool_call` /
    `tool_result` 事件归属到当前气泡，直至下一个 `message_start` 或 `done`。

    SSE 事件类型：
      message_start  — {"type": "message_start", "id": "..."}（新气泡边界）
      reasoning      — {"type": "reasoning", "content": "..."}
      reasoning_done — {"type": "reasoning_done", "duration_ms": int}
      token          — {"type": "token", "content": "..."}
      tool_call      — {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}, "display": "..."}
      tool_result    — {"type": "tool_result", "tool_call_id": "...", "name": "...", "content": "...", "duration_ms": int}
      done           — {"type": "done", "reason": "..."}（reason 仅 max_iterations 时有值）
      error          — {"type": "error", "content": "..."}
    """
    _ensure_system_prompt()
    history_snapshot_len = len(_history)
    _history.append({"role": "user", "content": user_message})

    # 本次用户输入产生的所有 assistant message_id（错误时统一回滚）
    new_message_ids: list[str] = []

    try:
        tool_schemas = get_tool_schemas()

        for _ in range(MAX_TOOL_ITERATIONS):
            message_id = uuid.uuid4().hex
            new_message_ids.append(message_id)
            msg_meta = _assistant_messages.setdefault(
                message_id, {"thinking": [], "tools": []}
            )
            yield {"type": "message_start", "id": message_id}

            stream = client.chat.completions.create(
                model=MODEL_ID,
                messages=_sanitize_for_openai(_history),
                tools=tool_schemas,
                max_tokens=MAX_TOKENS,
                stream=True,
            )

            text_parts, accumulated, finish_reason, thinking_segments = yield from _accumulate_stream(stream)

            if thinking_segments:
                msg_meta["thinking"].extend(thinking_segments)

            # 分支：纯文本回复 → 结束
            if finish_reason != "tool_calls" or not accumulated:
                yield from _on_text_response(text_parts, message_id)
                return

            # 分支：工具调用 → 执行后继续循环
            yield from _on_tool_calls(text_parts, accumulated, message_id)

        yield {"type": "done", "reason": "max_iterations_reached"}

    except Exception as e:
        # 回滚到 user 消息追加之前的状态
        del _history[history_snapshot_len:]
        for mid in new_message_ids:
            _assistant_messages.pop(mid, None)
        yield {"type": "error", "content": str(e)}
