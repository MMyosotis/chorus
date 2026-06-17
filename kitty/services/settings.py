"""SettingsService：进程级动态配置（如 image_test_mode）。

替代旧 config._image_test_mode 全局 + SettingsStore。内存 cache + 持久化双写，
启动时 load_all 回灌。generate_image 工具与 /api/debug/test-mode 均经此读写。
"""

from __future__ import annotations

import threading
from typing import Any

from kitty.repositories.settings import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository):
        self._repo = repo
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def load_all(self) -> None:
        with self._lock:
            self._cache = self._repo.all()

    def get_image_test_mode(self) -> bool:
        return bool(self._cache.get("image_test_mode", False))

    def set_image_test_mode(self, enabled: bool) -> None:
        self.set_raw("image_test_mode", bool(enabled))

    def get_raw(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def set_raw(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
            self._repo.set(key, value)
