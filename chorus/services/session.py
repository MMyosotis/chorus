"""SessionService：会话元数据编排（元数据 CRUD + per-session 锁 + 内存缓存）。

收窄后只管会话概念本身：create/list/get/delete/rename/set_title_if_unset/get_lock。
消息 / trace 的写入与读取归 MessageService；session 的 updated_at 刷新由编排层
（ChatService）在消息落库后调 touch() 触发——跨概念协调归编排，不在此处。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Callable

from chorus.domain.session import Session, SessionSummary
from chorus.domain.title import STORED_TITLE_MAX_LEN, normalize_title
from chorus.repositories.session import SessionRepository


class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        clock: Callable[[], float] = time.time,
    ):
        self._session_repo = session_repo
        self._clock = clock

        self._global_lock = threading.Lock()
        self._session_locks: dict[str, threading.Lock] = {}
        self._meta_cache: dict[str, Session] = {}

    # 启动 / 元数据 CRUD
    def load(self) -> None:
        with self._global_lock:
            self._meta_cache.clear()
            self._session_locks.clear()
            for session in self._session_repo.list_all():
                self._meta_cache[session.id] = session
                self._session_locks[session.id] = threading.Lock()

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
        # 用户手改：严格校验，空/超长都拒绝；只 strip 不截断，故不用会截断的 normalize_title。
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
        # 自动标题：宽容归一化（空→跳过，超长→截断），不打扰用户。
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

    def touch(self, session_id: str) -> None:
        """刷新会话 updated_at（列表排序依据）。由编排层在消息落库后调用。"""
        now = self._clock()
        self._session_repo.update_meta(session_id, updated_at=now)
        with self._global_lock:
            session = self._meta_cache.get(session_id)
        if session is not None:
            self._replace_cache(session.model_copy(update={"updated_at": now}))

    # 锁
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

    # 内部
    def _replace_cache(self, session: Session) -> None:
        with self._global_lock:
            self._meta_cache[session.id] = session
