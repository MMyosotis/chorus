import json

from openai import OpenAI

from backend.config import (
    API_KEY,
    BASE_URL,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
    MODEL_ID,
    SYSTEM_PROMPT,
)
from backend.tools import dispatch_tool, get_tool_schemas

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 全局单会话历史
_history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]


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


def get_history() -> list[dict]:
    """返回 user/assistant/tool 消息（不含 system）。"""
    return [m for m in _history if m["role"] != "system"]


def reset_history():
    """重置对话历史。"""
    global _history
    _history = [{"role": "system", "content": _build_system_prompt()}]


def _accumulate_stream(stream):
    """消费流式响应，yield token 事件，返回 (text_parts, accumulated_tool_calls, finish_reason)。"""
    accumulated: dict[int, dict] = {}
    text_parts: list[str] = []
    finish_reason = None

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta
        if choice.finish_reason is not None:
            finish_reason = choice.finish_reason

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

    return text_parts, accumulated, finish_reason


def _on_text_response(text_parts: list[str]):
    """模型返回纯文本（未调用工具）：写入历史，yield done。"""
    full_text = "".join(text_parts)
    if full_text:
        _history.append({"role": "assistant", "content": full_text})
    yield {"type": "done"}


def _on_tool_calls(text_parts: list[str], accumulated: dict[int, dict]):
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
    })

    for tc in tool_calls_list:
        tool_name = tc["function"]["name"]
        try:
            tool_args = json.loads(tc["function"]["arguments"])
        except json.JSONDecodeError:
            tool_args = {}

        yield {"type": "tool_call", "id": tc["id"], "name": tool_name, "arguments": tool_args}

        result = dispatch_tool(tool_name, tool_args)

        yield {"type": "tool_result", "tool_call_id": tc["id"], "name": tool_name, "content": result}

        _history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})


# noinspection PyTypeChecker
def chat_stream(user_message: str):
    """流式 agent loop，支持 tool calling。每次 yield 一个事件 dict。

    SSE 事件类型：
      token       — {"type": "token", "content": "..."}
      tool_call   — {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}}
      tool_result — {"type": "tool_result", "tool_call_id": "...", "name": "...", "content": "..."}
      done        — {"type": "done", "reason": "..."}（reason 仅异常时有值）
      error       — {"type": "error", "content": "..."}
    """
    _ensure_system_prompt()
    _history.append({"role": "user", "content": user_message})

    try:
        tool_schemas = get_tool_schemas()

        for _ in range(MAX_TOOL_ITERATIONS):
            stream = client.chat.completions.create(
                model=MODEL_ID,
                messages=_history,
                tools=tool_schemas,
                max_tokens=MAX_TOKENS,
                stream=True,
            )

            text_parts, accumulated, finish_reason = yield from _accumulate_stream(stream)

            # 分支：纯文本回复 → 结束
            if finish_reason != "tool_calls" or not accumulated:
                yield from _on_text_response(text_parts)
                return

            # 分支：工具调用 → 执行后继续循环
            yield from _on_tool_calls(text_parts, accumulated)

        yield {"type": "done", "reason": "max_iterations_reached"}

    except Exception as e:
        _history.pop()  # 回滚 user 消息
        yield {"type": "error", "content": str(e)}
