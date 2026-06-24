"""MessageService：消息 + trace 的应用编排（编排 MessageRepository + TraceRepository）。

消息逐条 append 入库（入库时机 = 产生时机）；build_provider_messages 是传给 LLM 的
消息序列唯一构建函数（转发 domain.build_provider_messages）；history_view 的
thinking/tools 由 trace 聚合重建（转发 domain.build_history_view）。
"""

from __future__ import annotations

import sqlite3
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

    def append_user_message(self, session_id: str, content: str, *, subtype: Optional[str] = None) -> UserMessage:
        return self._append_with_retry(
            session_id,
            lambda seq: UserMessage(id=uuid.uuid4().hex, session_id=session_id, seq=seq,
                                    created_at=self._clock(), content=content, subtype=subtype),
        )

    def append_assistant_message(
        self, session_id: str, *, message_id: str, content: Optional[str],
        tool_calls: list[ToolCallSpec], subtype: Optional[str] = None,
    ) -> AssistantMessage:
        return self._append_with_retry(
            session_id,
            lambda seq: AssistantMessage(id=message_id, session_id=session_id, seq=seq,
                                         created_at=self._clock(), content=content,
                                         tool_calls=tool_calls, subtype=subtype),
        )

    def append_tool_message(
        self, session_id: str, *, tool_call_id: str, name: str, content: str,
        subtype: Optional[str] = None,
    ) -> ToolMessage:
        return self._append_with_retry(
            session_id,
            lambda seq: ToolMessage(id=uuid.uuid4().hex, session_id=session_id, seq=seq,
                                    created_at=self._clock(), tool_call_id=tool_call_id,
                                    name=name, content=content, subtype=subtype),
        )

    def append_progress_message(self, session_id: str, *, message_id: str, content: str) -> AssistantMessage:
        """进度气泡（subtype=progress）：subagent enter/done 节点用。"""
        return self.append_assistant_message(
            session_id, message_id=message_id, content=content,
            tool_calls=[], subtype="progress",
        )

    def _append_with_retry(self, session_id: str, factory) -> Message:
        """并发 append 撞 UNIQUE(session_id, seq) 时重试重取 seq（bounded 10 次 + 微退避）。

        next_seq(读 MAX+1) 与 INSERT 非原子，多 subagent 线程并发 append 同 session
        时会抢同一 seq 槽。重试重取 seq + 微退避让抢同一槽的线程错开，bounded 上限
        兜底极端争用（仍失败则上抛，由调用方视为主流程错误）。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(10):
            msg = factory(self._msg_repo.next_seq(session_id))
            try:
                self._msg_repo.append(msg)
                return msg
            except sqlite3.IntegrityError as e:
                last_exc = e
                time.sleep(0.001 * (attempt + 1))  # 1ms 起步线性退避，错开抢槽线程
                continue
        raise last_exc

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
