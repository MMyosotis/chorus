"""CleanupService：会话清理的应用编排（节流 + 取数据 + 调领域策略）。

纯清理策略在 domain.cleanup.select_cleanup；本类只负责节流判断、
从 repo 取数据喂给策略、返回 CleanupDecision。实际删除（带会话锁）由
SessionService 执行，避免循环依赖。
"""

from __future__ import annotations

import time
from typing import Callable

from kitty.domain.cleanup import CleanupDecision, select_cleanup
from kitty.repositories.session import SessionRepository
from kitty.repositories.message import MessageRepository


class CleanupService:
    def __init__(
        self,
        session_repo: SessionRepository,
        msg_repo: MessageRepository,
        ttl_days: int,
        max_bytes: int,
        max_count: int,
        clock: Callable[[], float] = time.time,
        throttle_seconds: int = 60,
    ):
        self._session_repo = session_repo
        self._msg_repo = msg_repo
        self._ttl_days = ttl_days
        self._max_bytes = max_bytes
        self._max_count = max_count
        self._clock = clock
        self._throttle_seconds = throttle_seconds
        self._last_run: float = 0.0

    def select(self, force: bool = False) -> CleanupDecision:
        """选出待删 id（不删除）。节流期内且非 force 返回 throttled 空决策。"""
        now = self._clock()
        if not force and (now - self._last_run) < self._throttle_seconds:
            return CleanupDecision(throttled=True)
        self._last_run = now

        sessions = self._session_repo.list_all()
        if len(sessions) <= 1:
            return CleanupDecision()

        oversize_ids = set(self._msg_repo.list_oversize(self._max_bytes))
        return select_cleanup(
            sessions, oversize_ids, self._ttl_days, self._max_count, now
        )
