from openai import OpenAI

from backend.config import API_KEY, BASE_URL, MODEL_ID, SYSTEM_PROMPT, MAX_TOKENS

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 全局单会话历史
_history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]


def get_history() -> list[dict]:
    """返回 user/assistant 消息（不含 system）"""
    return [m for m in _history if m["role"] != "system"]


def reset_history():
    """重置对话历史"""
    global _history
    _history = [{"role": "system", "content": SYSTEM_PROMPT}]


def chat_stream(user_message: str):
    """流式生成器，SSE 使用。每次 yield 一个 token 字符串。"""
    _history.append({"role": "user", "content": user_message})
    try:
        # noinspection PyTypeChecker
        stream = client.chat.completions.create(
            model=MODEL_ID,
            messages=_history,
            max_tokens=MAX_TOKENS,
            stream=True,
        )
        collected = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                collected.append(delta.content)
                yield delta.content
        # 流结束后，将完整回复写入历史
        full_reply = "".join(collected)
        _history.append({"role": "assistant", "content": full_reply})
    except Exception as e:
        # 发生错误时移除已追加的 user 消息，向上抛出
        _history.pop()
        raise e
