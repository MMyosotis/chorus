"""消息服务：消息的应用编排，双表双写，转发领域函数构建模型输入与前端视图。

原表存最原始事实供前端读，现场表存发给模型的压缩结果；视图的思考与工具摘要
由轨迹聚合重建，轨迹经批量预取避免逐条查询。
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
    build_history_view,
    build_provider_messages,
)
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.services.compact import CompactService
from chorus.services.trace import TraceService


class MessageService:
    def __init__(
        self,
        msg_repo: MessageRepository,
        provider_repo: ProviderMessageRepository,
        trace_service: TraceService,
        compact: CompactService,
    ):
        self._msg_repo = msg_repo
        self._provider_repo = provider_repo
        self._trace = trace_service
        self._compact = compact

    def list_messages(self, session_id: str) -> list[Message]:
        return self._msg_repo.list_by_session(session_id)

    def append_user_message(self, session_id: str, content: str) -> UserMessage:
        msg = UserMessage(
            id=str(uuid6.uuid7()),
            session_id=session_id,
            created_at=time.time(),
            content=content,
        )
        self._append_both(msg)
        return msg

    def append_assistant_message(
        self, session_id: str, *, message_id: str, content: Optional[str],
        tool_calls: Optional[list[ToolCallSpec]] = None,
    ) -> AssistantMessage:
        msg = AssistantMessage(
            id=message_id,
            session_id=session_id,
            created_at=time.time(),
            content=content,
            tool_calls=tool_calls or [],
        )
        self._append_both(msg)
        return msg

    def append_error_placeholder(self, session_id: str, message_id: str, error: Exception) -> None:
        """异常时写入的助手占位行，关闭前端气泡。"""
        msg = AssistantMessage(
            id=message_id,
            session_id=session_id,
            created_at=time.time(),
            content=f"[Error] {error}",
        )
        self._append_both(msg)

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
        self._append_both(msg)
        return msg

    def _append_both(self, msg: Message) -> None:
        """正常新消息双表双写：两表行同标识，前端读原表、模型读现场表。"""
        self._msg_repo.append(msg)
        self._provider_repo.append(msg)

    def rewrite_last_tool_result(self, session_id: str, name: str, content: str) -> None:
        """改写会话内最后一条该名工具的结果，供用户拍板后补全真实结局。"""
        target = self._msg_repo.find_last_tool_by_name(session_id, name)
        self._msg_repo.update_content(target.id, content)
        self._provider_repo.update_content(target.id, content)

    def history_view(self, session_id: str) -> list[MessageView]:
        """前端视图：读原表全量，助手消息挂回思考与工具摘要，轨迹批量预取。"""
        msgs = self._msg_repo.list_by_session(session_id)
        traces = self._trace.batch_aggregate(
            [message.id for message in msgs if message.role == "assistant"]
        )
        return build_history_view(msgs, traces)

    # 模型输入消息序列唯一构建点
    def build_provider_messages(self, session_id: str, system_prompt: str) -> list[dict]:
        """构建发给模型的消息序列：系统提示加现场表历史，压缩已写时落定。"""
        return build_provider_messages(system_prompt, self._compact.ensure_active(session_id))
