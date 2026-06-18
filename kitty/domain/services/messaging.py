"""消息序列构造领域逻辑。

- build_provider_messages：组装发给 LLM 的消息序列（[system] + 历史消息的 provider dict）。
- build_history_view：组装前端视图（过滤 tool，assistant 挂回 thinking/tools 元数据）。

两者纯领域：输入领域模型，输出 dict / MessageView，不碰 repo。
"""

from __future__ import annotations

from typing import Callable, Iterable

from kitty.domain.models.message import (
    AssistantMessage,
    Message,
    MessageView,
    UserMessage,
)
from kitty.domain.models.trace import MessageTrace


def build_provider_messages(system_prompt: str, messages: Iterable[Message]) -> list[dict]:
    """构建发给 LLM 的消息序列：[system] + 历史消息（按 seq，各角色自行 to_provider_dict）。"""
    result: list[dict] = [{"role": "system", "content": system_prompt}]
    result.extend(m.to_provider_dict() for m in messages)
    return result


def build_history_view(
    messages: Iterable[Message],
    trace_of: Callable[[str], MessageTrace],
) -> list[MessageView]:
    """前端视图：过滤 tool，assistant 挂回 thinking/tools（由 trace_of 取每条 assistant 的聚合 trace）。

    trace_of 是注入的回调（实际由 TraceRepository.aggregate_message_trace 提供），
    本函数不依赖 repo。
    """
    result: list[MessageView] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            result.append(MessageView(id=msg.id, role="user", content=msg.content))
        elif isinstance(msg, AssistantMessage):
            trace = trace_of(msg.id)
            result.append(
                MessageView(
                    id=msg.id,
                    role="assistant",
                    content=msg.content or "",
                    thinking=trace.thinking,
                    tools=trace.tools,
                )
            )
    return result
