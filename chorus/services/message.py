"""MessageService：消息的应用编排（编排 MessageRepository，消费 TraceService）。

消息逐条 append 入库（入库时机 = 产生时机）；build_provider_messages 是传给 LLM 的
消息序列唯一构建函数（转发 domain.build_provider_messages）；history_view 的
thinking/tools 由 trace 聚合重建（转发 domain.build_history_view）——trace 预取经
TraceService.batch_aggregate。
"""

from __future__ import annotations

import time
from typing import Optional

import uuid6

from chorus.domain.message import (
    AssistantMessage,
    Message,
    MessageView,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from chorus.domain.message import build_history_view, build_provider_messages
from chorus.repo.message import MessageRepository
from chorus.services.trace import TraceService


class MessageService:
    def __init__(self, msg_repo: MessageRepository, trace_service: TraceService):
        self._msg_repo = msg_repo
        self._trace = trace_service

    def list_messages(self, session_id: str) -> list[Message]:
        return self._msg_repo.list_by_session(session_id)

    def append_user_message(self, session_id: str, content: str) -> UserMessage:
        msg = UserMessage(
            id=str(uuid6.uuid7()),
            session_id=session_id,
            created_at=time.time(),
            content=content,
        )
        self._msg_repo.append(msg)
        return msg

    def append_assistant_message(
        self, session_id: str, *, message_id: str, content: Optional[str], tool_calls: list[ToolCallSpec],
    ) -> AssistantMessage:
        msg = AssistantMessage(
            id=message_id,
            session_id=session_id,
            created_at=time.time(),
            content=content,
            tool_calls=tool_calls,
        )
        self._msg_repo.append(msg)
        return msg

    def append_tool_message(
        self, session_id: str, *, tool_call_id: str, name: str, content: str,
    ) -> ToolMessage:
        msg = ToolMessage(
            id=str(uuid6.uuid7()),
            session_id=session_id,
            created_at=time.time(),
            tool_call_id=tool_call_id,
            name=name,
            content=content,
        )
        self._msg_repo.append(msg)
        return msg

    def history_view(self, session_id: str) -> list[MessageView]:
        """前端视图：过滤 tool/system，assistant 挂回 thinking/tools（从 trace 聚合）。

        trace 批量预取经 TraceService（一次 IN 查询），避免在 domain 内逐条查（N+1）。
        """
        msgs = self._msg_repo.list_by_session(session_id)
        traces = self._trace.batch_aggregate(
            [m.id for m in msgs if isinstance(m, AssistantMessage)]
        )
        return build_history_view(msgs, traces)

    # provider_messages 唯一构建点
    def build_provider_messages(self, session_id: str, system_prompt: str) -> list[dict]:
        """构建发给 LLM 的消息序列：[system] + 该会话全部历史消息（按 id 升序）。"""
        return build_provider_messages(system_prompt, self._msg_repo.list_by_session(session_id))
