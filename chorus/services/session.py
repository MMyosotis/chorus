"""会话服务：会话元数据增删改查 + 标题归一。

只管会话概念本身，消息与轨迹归消息服务；无缓存直打库，标题复检加写入靠 SQL 原子。
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from chorus.domain.session import Session, SessionSummary
from chorus.domain.title import STORED_TITLE_MAX_LEN, normalize_title
from chorus.repo.session import SessionRepository


class SessionService:
    def __init__(self, session_repo: SessionRepository):
        self._session_repo = session_repo

    # 元数据 CRUD
    def list(self) -> list[SessionSummary]:
        sessions = self._session_repo.list_all()
        return [
            SessionSummary(id=session.id, title=session.title, created_at=session.created_at, updated_at=session.updated_at)
            for session in sessions
        ]

    def get(self, session_id: str) -> Optional[Session]:
        return self._session_repo.get(session_id)

    def exists(self, session_id: str) -> bool:
        return self._session_repo.get(session_id) is not None

    def create(self, title: str = "新对话") -> Session:
        cid = uuid.uuid4().hex
        now = time.time()
        session = Session(
            id=cid, title=title, title_generated=False, created_at=now, updated_at=now
        )
        self._session_repo.insert(session)
        return session

    def delete(self, session_id: str) -> None:
        self._session_repo.delete(session_id)  # CASCADE 带走消息与轨迹；删 0 行幂等

    def rename(self, session_id: str, title: str) -> Optional[Session]:
        # 用户手改：严格校验，空或超长拒绝，只去空白不截断
        title = (title or "").strip()
        if not title:
            raise ValueError("title 不能为空")
        if len(title) > STORED_TITLE_MAX_LEN:
            raise ValueError(f"title 长度不能超过 {STORED_TITLE_MAX_LEN}")
        self._session_repo.set_title(
            session_id, title=title, title_generated=True, updated_at=time.time()
        )
        return self.get(session_id)

    def is_title_set(self, session_id: str) -> bool:
        """标题是否已确定，供调用方在昂贵操作前短路。会话不存在视为未定名。"""
        session = self.get(session_id)
        return session is not None and session.title_generated

    def set_title(self, session_id: str, title: str) -> bool:
        """落自动标题：宽容归一化，空则跳过超长则截断。"""
        title = normalize_title(title)
        if not title:
            return False
        self._session_repo.set_title(
            session_id, title=title, title_generated=True, updated_at=time.time()
        )
        return True

    def touch(self, session_id: str) -> None:
        """刷新会话更新时间，列表排序依据，由编排层在消息落库后调用。"""
        self._session_repo.touch(session_id, time.time())
