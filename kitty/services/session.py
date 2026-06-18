"""SessionService：会话业务编排（编排 3 个 Repository + 锁 + 清理）。

阶段 2 核心改造（见 plan M1/M2/M6）：
- 逐条 append 入库（替代旧 store.save 全量重写）—— 入库时机 = 消息产生时机；
- build_provider_messages 是传给 LLM 的消息序列的【唯一】构建函数（plan 检验1 支点）；
- history_view 的 thinking/tools 由 TraceRepository.aggregate_message_trace 重建，
  messages 与 traces 物理解耦（plan 检验4）。

不持 SQL（经 Repository），不感知 HTTP（由 routes 适配）。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Callable, Optional

from kitty.domain.models.session import Session, SessionSummary
from kitty.domain.models.message import (
    AssistantMessage,
    Message,
    MessageView,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from kitty.domain.models.trace import TraceEntry
from kitty.domain.services.messaging import build_history_view, build_provider_messages
from kitty.domain.services.title import STORED_TITLE_MAX_LEN, normalize_title
from kitty.repositories.session import SessionRepository
from kitty.repositories.message import MessageRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.cleanup import CleanupService


class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        msg_repo: MessageRepository,
        trace_repo: TraceRepository,
        cleanup_service: CleanupService,
        clock: Callable[[], float] = time.time,
    ):
        self._session_repo = session_repo
        self._msg_repo = msg_repo
        self._trace_repo = trace_repo
        self._cleanup = cleanup_service
        self._clock = clock

        self._global_lock = threading.Lock()
        self._session_locks: dict[str, threading.Lock] = {}
        self._meta_cache: dict[str, Session] = {}

    # ------------------------------------------------------------------
    # 启动 / 元数据 CRUD
    # ------------------------------------------------------------------
    def load(self) -> None:
        with self._global_lock:
            self._meta_cache.clear()
            self._session_locks.clear()
            for session in self._session_repo.list_all():
                self._meta_cache[session.id] = session
                self._session_locks[session.id] = threading.Lock()
        self._maybe_cleanup(force=True)

    def list(self) -> list[SessionSummary]:
        with self._global_lock:
            sessions = list(self._meta_cache.values())
        sessions.sort(key=lambda c: c.updated_at, reverse=True)
        return [
            SessionSummary(id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at)
            for c in sessions
        ]

    def get(self, session_id: str) -> Session:
        with self._global_lock:
            session = self._meta_cache.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def exists(self, session_id: str) -> bool:
        with self._global_lock:
            return session_id in self._meta_cache

    def create(self, title: str = "新对话") -> Session:
        cid = uuid.uuid4().hex
        now = self._clock()
        session = Session(
            id=cid, title=title, title_generated=False, created_at=now, updated_at=now
        )
        self._session_repo.insert(session)
        with self._global_lock:
            self._meta_cache[cid] = session
            self._session_locks[cid] = threading.Lock()
        return session

    def delete(self, session_id: str) -> None:
        with self._global_lock:
            if session_id not in self._meta_cache:
                raise KeyError(session_id)
            self._meta_cache.pop(session_id, None)
            self._session_locks.pop(session_id, None)
        self._session_repo.delete(session_id)  # CASCADE 带走 messages / traces

    def rename(self, session_id: str, title: str) -> Session:
        # 用户手改标题：严格校验（空/超长都拒绝，提示用户而非静默截断）。
        # 只 strip 不截断——超长要报错，故不用会截断的 normalize_title。
        title = (title or "").strip()
        if not title:
            raise ValueError("title 不能为空")
        if len(title) > STORED_TITLE_MAX_LEN:
            raise ValueError(f"title 长度不能超过 {STORED_TITLE_MAX_LEN}")
        session = self.get(session_id)
        now = self._clock()
        with self.get_lock(session_id):
            updated = session.model_copy(
                update={"title": title, "title_generated": True, "updated_at": now}
            )
            self._session_repo.update_meta(
                session_id, title=title, title_generated=True, updated_at=now
            )
        self._replace_cache(updated)
        return updated

    def set_title_if_unset(self, session_id: str, title: str) -> bool:
        # 自动标题：宽容归一化（空→跳过，超长→截断，不打扰用户）。
        title = normalize_title(title)
        if not title:
            return False
        session = self.get(session_id)
        with self.get_lock(session_id):
            if session.title_generated:
                return False
            now = self._clock()
            updated = session.model_copy(
                update={"title": title, "title_generated": True, "updated_at": now}
            )
            self._session_repo.update_meta(
                session_id, title=title, title_generated=True, updated_at=now
            )
        self._replace_cache(updated)
        return True

    # ------------------------------------------------------------------
    # 消息（逐条入库）
    # ------------------------------------------------------------------
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
        self._append_and_touch(msg)
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
        self._append_and_touch(msg)
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
        self._append_and_touch(msg)
        return msg

    def truncate_after_snapshot(
        self, session_id: str, snapshot_len: int, drop_message_ids: list[str]
    ) -> None:
        """rollback 用：删除 seq >= snapshot_len 的消息 + 对应 trace。"""
        self._msg_repo.delete_after_seq(session_id, snapshot_len)
        for mid in drop_message_ids:
            self._trace_repo.delete_by_message(mid)

    def history_view(self, session_id: str) -> list[MessageView]:
        """前端视图：过滤 tool/system，assistant 挂回 thinking/tools（从 trace 聚合）。

        领域组装规则在 domain.services.messaging.build_history_view，本方法只取数据喂它。
        """
        return build_history_view(
            self._msg_repo.list_by_session(session_id),
            self._trace_repo.aggregate_message_trace,
        )

    # ------------------------------------------------------------------
    # ★ 唯一的 provider_messages 构建函数（plan 检验1 支点）
    # ------------------------------------------------------------------
    def build_provider_messages(self, session_id: str, system_prompt: str) -> list[dict]:
        """构建发给 LLM 的消息序列：[system] + 该会话全部历史消息（按 seq，各角色自行映射）。

        因采用逐条入库，调用时历史已全部落 messages 表，本轮 user 消息也已 append，
        故此处读到的就是"截至本轮的完整历史"。领域组装规则在
        domain.services.messaging.build_provider_messages，本方法只取数据喂它。
        """
        return build_provider_messages(system_prompt, self._msg_repo.list_by_session(session_id))

    # ------------------------------------------------------------------
    # Trace
    # ------------------------------------------------------------------
    def add_trace(self, entry: TraceEntry) -> None:
        self._trace_repo.add(entry)

    def list_traces(self, session_id: str) -> list[TraceEntry]:
        return self._trace_repo.list_by_session(session_id)

    # ------------------------------------------------------------------
    # 锁
    # ------------------------------------------------------------------
    def get_lock(self, session_id: str) -> threading.Lock:
        """返回该会话的锁对象（routes SSE 端点用 acquire(blocking=False) 探测并发）。"""
        with self._global_lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                if session_id not in self._meta_cache:
                    raise KeyError(session_id)
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    # ------------------------------------------------------------------
    # 清理执行（策略在 CleanupService，删除带锁由本类执行）
    # ------------------------------------------------------------------
    def cleanup(self, force: bool = False) -> None:
        self._maybe_cleanup(force)

    def _maybe_cleanup(self, force: bool = False) -> None:
        report = self._cleanup.select(force)
        if report.throttled or not report.selected_ids:
            return
        for cid in report.selected_ids:
            self._cleanup_delete(cid)

    def _cleanup_delete(self, session_id: str) -> None:
        with self._global_lock:
            if session_id not in self._meta_cache:
                return
            if len(self._meta_cache) <= 1:
                return
            lock = self._session_locks.get(session_id)
        if lock is None or not lock.acquire(blocking=False):
            return
        try:
            self.delete(session_id)
        except Exception:
            pass
        finally:
            lock.release()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _append_and_touch(self, msg: Message) -> None:
        """单条消息入库 + 刷新会话 updated_at（cache 与 repo 同步）。"""
        self._msg_repo.append(msg)
        now = msg.created_at
        self._session_repo.update_meta(msg.session_id, updated_at=now)
        with self._global_lock:
            session = self._meta_cache.get(msg.session_id)
        if session is not None:
            self._replace_cache(session.model_copy(update={"updated_at": now}))
        self._maybe_cleanup()

    def _replace_cache(self, session: Session) -> None:
        with self._global_lock:
            self._meta_cache[session.id] = session
