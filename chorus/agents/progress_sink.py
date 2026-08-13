"""流式正文进度快照写入器:逐字累计字数与结构单元,节流覆盖写。"""
from __future__ import annotations

from time import perf_counter

from chorus.domain.task.progress import UnitCounter
from chorus.repo.task_progress import TaskProgressRepository


class ProgressSink:
    """逐字累计正文量与结构单元,节流覆盖写进度快照。"""

    def __init__(self, task_id: str, repo: TaskProgressRepository, marker: str | None = None):
        self._task_id = task_id
        self._repo = repo
        self._counter = UnitCounter(marker) if marker else None
        self._chars = 0
        self._last_flush_at = perf_counter()
        self._last_flush_chars = 0

    def feed(self, content: str) -> None:
        was_empty = self._chars == 0
        self._chars += len(content)
        if self._counter is not None:
            self._counter.feed(content)
        if was_empty:
            self._repo.set_activity(self._task_id, "composing")
        now = perf_counter()
        if self._chars - self._last_flush_chars < 16 and now - self._last_flush_at < 0.5:
            return
        self._flush()
        self._last_flush_chars = self._chars
        self._last_flush_at = now

    def _flush(self) -> None:
        if self._counter is not None:
            self._repo.set_composing(self._task_id, self._chars, self._counter.count)
        else:
            self._repo.set_composing_chars(self._task_id, self._chars)
