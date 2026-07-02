"""消息服务：消息的应用编排，逐条入库，转发领域函数构建模型输入与前端视图。

视图的思考与工具摘要由轨迹聚合重建，轨迹经批量预取避免逐条查询。
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
        """前端视图：滤掉工具消息，助手消息挂回思考与工具摘要，轨迹批量预取。"""
        msgs = self._msg_repo.list_by_session(session_id)
        traces = self._trace.batch_aggregate(
            [m.id for m in msgs if isinstance(m, AssistantMessage)]
        )
        return build_history_view(msgs, traces)

    # 模型输入消息序列唯一构建点
    def build_provider_messages(self, session_id: str, system_prompt: str) -> list[dict]:
        """构建发给模型的消息序列：系统提示加该会话全部历史消息。"""
        return build_provider_messages(system_prompt, self._msg_repo.list_by_session(session_id))
