"""会话清理策略领域逻辑（纯策略，不删除）。

select_cleanup：给定一组 session 元数据 + 超额字节集合 + 阈值，选出待删 id。
删除本身（带会话锁）由 application 层的 CleanupService 执行，避免循环依赖。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kitty.domain.session import Session


@dataclass(frozen=True)
class CleanupDecision:
    """清理决策：按 TTL / 超字节 / 总量溢出三类选出待删 session_id。"""

    throttled: bool = False
    ttl_ids: list[str] = field(default_factory=list)
    oversize_ids: list[str] = field(default_factory=list)
    overflow_ids: list[str] = field(default_factory=list)

    @property
    def selected_ids(self) -> list[str]:
        return self.ttl_ids + self.oversize_ids + self.overflow_ids


def select_cleanup(
    sessions: list[Session],
    oversize_ids: set[str],
    ttl_days: int,
    max_count: int,
    now: float,
) -> CleanupDecision:
    """选出待删 id（不删除）。sessions 应已排除「仅剩一条」的空库保护场景。"""
    ttl_cut = _ttl_cut(now, ttl_days)

    ttl_ids: list[str] = []
    oversize_ids_hit: list[str] = []
    for c in sessions:
        if ttl_cut is not None and c.updated_at < ttl_cut:
            ttl_ids.append(c.id)
        elif c.id in oversize_ids:
            oversize_ids_hit.append(c.id)

    already = set(ttl_ids) | set(oversize_ids_hit)
    overflow_ids = _select_overflow(sessions, already, max_count)
    return CleanupDecision(
        ttl_ids=ttl_ids, oversize_ids=oversize_ids_hit, overflow_ids=overflow_ids
    )


def _ttl_cut(now: float, ttl_days: int) -> float | None:
    if ttl_days <= 0:
        return None
    return now - ttl_days * 86400


def _select_overflow(sessions: list[Session], already: set[str], max_count: int) -> list[str]:
    remaining = sorted(
        (c for c in sessions if c.id not in already),
        key=lambda c: c.updated_at,
    )
    excess = len(remaining) - max_count
    if excess <= 0:
        return []
    return [c.id for c in remaining[:excess]]
