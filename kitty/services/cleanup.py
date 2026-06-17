"""CleanupService：会话清理策略（TTL / 单会话字节数 / 总量）。

纯策略层 —— 只"选出要删的 session_id"，不实际删除（删除带会话锁，由
SessionService 执行），避免与 SessionService 循环依赖，且便于单测。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from kitty.repositories.session import SessionRepository
from kitty.repositories.message import MessageRepository


@dataclass
class CleanupReport:
    throttled: bool = False
    ttl_ids: list[str] = field(default_factory=list)
    oversize_ids: list[str] = field(default_factory=list)
    overflow_ids: list[str] = field(default_factory=list)

    @property
    def selected_ids(self) -> list[str]:
        return self.ttl_ids + self.oversize_ids + self.overflow_ids


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

    def select(self, force: bool = False) -> CleanupReport:
        """选出待删 id（不删除）。节流期内且非 force 返回 throttled 空报告。"""
        now = self._clock()
        if not force and (now - self._last_run) < self._throttle_seconds:
            return CleanupReport(throttled=True)
        self._last_run = now

        sessions = self._session_repo.list_all()
        if len(sessions) <= 1:
            return CleanupReport()

        ttl_cut = self._ttl_cut(now)
        oversize_set = set(self._msg_repo.list_oversize(self._max_bytes))

        ttl_ids: list[str] = []
        oversize_ids: list[str] = []
        for c in sessions:
            if ttl_cut is not None and c.updated_at < ttl_cut:
                ttl_ids.append(c.id)
            elif c.id in oversize_set:
                oversize_ids.append(c.id)

        already = set(ttl_ids) | set(oversize_ids)
        overflow_ids = self._select_overflow(sessions, already)
        return CleanupReport(ttl_ids=ttl_ids, oversize_ids=oversize_ids, overflow_ids=overflow_ids)

    def _ttl_cut(self, now: float) -> Optional[float]:
        if self._ttl_days <= 0:
            return None
        return now - self._ttl_days * 86400

    def _select_overflow(self, sessions, already: set[str]) -> list[str]:
        remaining = sorted(
            (c for c in sessions if c.id not in already),
            key=lambda c: c.updated_at,
        )
        excess = len(remaining) - self._max_count
        if excess <= 0:
            return []
        return [c.id for c in remaining[:excess]]
