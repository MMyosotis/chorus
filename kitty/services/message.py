"""MessageService：消息 + trace 的应用编排（编排 MessageRepository + TraceRepository）。

消息逐条 append 入库（入库时机 = 产生时机）；build_provider_messages 是传给 LLM 的
消息序列唯一构建函数（转发 domain.build_provider_messages）；history_view 的
thinking/tools 由 trace 聚合重建（转发 domain.build_history_view）。
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

from kitty.domain.message import (
    AssistantMessage,
    Message,
    MessageView,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from kitty.domain.message import build_history_view, build_provider_messages
from kitty.domain.trace import TraceEntry
from kitty.repositories.message import MessageRepository
from kitty.repositories.trace import TraceRepository


class MessageService:
    def __init__(
        self,
        msg_repo: MessageRepository,
        trace_repo: TraceRepository,
        clock: Callable[[], float] = time.time,
    ):
        self._msg_repo = msg_repo
        self._trace_repo = trace_repo
        self._clock = clock

    # 消息（逐条入库）
    def list_messages(self, session_id: str) -> list[Message]:
        return self._msg_repo.list_by_session(session_id)

    def append_user_message(self, session_id: str, content: str) -> UserMessage:
        msg = UserMessage(
            id=uuid.uuid4().hex,
            session_id=session_id,
            seq=self._msg_repo.next_seq(session_id),
            created_at=self._clock(),
            content=content,
        )
        self._msg_repo.append(msg)
        return msg

    def append_assistant_message(
        self,
        session_id: str,
        *,
        message_id: str,
        content: Optional[str],
        tool_calls: list[ToolCallSpec],
    ) -> AssistantMessage:
        msg = AssistantMessage(
            id=message_id,
            session_id=session_id,
            seq=self._msg_repo.next_seq(session_id),
            created_at=self._clock(),
            content=content,
            tool_calls=tool_calls,
        )
        self._msg_repo.append(msg)
        return msg

    def append_tool_message(
        self, session_id: str, *, tool_call_id: str, name: str, content: str
    ) -> ToolMessage:
        msg = ToolMessage(
            id=uuid.uuid4().hex,
            session_id=session_id,
            seq=self._msg_repo.next_seq(session_id),
            created_at=self._clock(),
            tool_call_id=tool_call_id,
            name=name,
            content=content,
        )
        self._msg_repo.append(msg)
        return msg

    def history_view(self, session_id: str) -> list[MessageView]:
        """前端视图：过滤 tool/system，assistant 挂回 thinking/tools（从 trace 聚合）。"""
        return build_history_view(
            self._msg_repo.list_by_session(session_id),
            self._trace_repo.aggregate_message_trace,
        )

    # provider_messages 唯一构建点
    def build_provider_messages(self, session_id: str, system_prompt: str) -> list[dict]:
        """构建发给 LLM 的消息序列：[system] + 该会话全部历史消息（按 seq）。"""
        return build_provider_messages(system_prompt, self._msg_repo.list_by_session(session_id))

    # Trace
    def add_trace(self, entry: TraceEntry) -> None:
        self._trace_repo.add(entry)

    def list_traces(self, session_id: str) -> list[TraceEntry]:
        return self._trace_repo.list_by_session(session_id)
