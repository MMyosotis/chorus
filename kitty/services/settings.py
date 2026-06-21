"""SettingsService：进程级动态配置（如 image_test_mode）。

内存 cache + 持久化双写，启动时 load_all 回灌。
"""

from __future__ import annotations

import threading
from typing import Any

from kitty.config import (
    CHAT_MODELS,
    DEFAULT_CHAT_MODEL_ID,
    DEFAULT_IMAGE_MODEL_ID,
    IMAGE_MODELS,
)
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

    # —— 输入框下方模型选项栏的进程级设置 ——
    def get_chat_model(self) -> str:
        # 校验已存值是否仍在配置表中（配置删模型/迁移后旧值自动回退默认）
        value = self._cache.get("chat_model")
        if value and any(m["id"] == value for m in CHAT_MODELS):
            return value
        return DEFAULT_CHAT_MODEL_ID

    def set_chat_model(self, value: str) -> None:
        self.set_raw("chat_model", value)

    def get_image_model(self) -> str:
        # 校验已存值是否仍在配置表中（配置删模型/迁移后旧值自动回退默认）
        value = self._cache.get("image_model")
        if value and any(m["id"] == value for m in IMAGE_MODELS):
            return value
        return DEFAULT_IMAGE_MODEL_ID

    def set_image_model(self, value: str) -> None:
        self.set_raw("image_model", value)

    def get_web_search(self) -> bool:
        return bool(self._cache.get("web_search", True))

    def set_web_search(self, enabled: bool) -> None:
        self.set_raw("web_search", bool(enabled))

    def get_raw(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def set_raw(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
            self._repo.set(key, value)
