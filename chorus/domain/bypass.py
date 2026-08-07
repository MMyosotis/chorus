"""旁路 LLM 调用：agent loop 之外的非流式单轮调用机制。"""
from __future__ import annotations

from openai import OpenAI


def call_once(client: OpenAI, model_id: str, prompt: str, max_tokens: int) -> str:
    """非流式单轮调用，返回去空白后的完整正文，异常上抛交调用方。"""
    resp = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        stream=False,
    )
    return (resp.choices[0].message.content or "").strip()
