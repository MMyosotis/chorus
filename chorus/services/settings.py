"""SettingsService：进程级动态配置（如 image_test_mode / 模型选择 / 联网搜索）。

直接读写 settings 表，无内存缓存——读多写少场景下 DB 往返可接受，换来无需维护
cache 与持久化的一致性。值的校验/默认在此层完成，repo 只做 KV 存取。
"""

from __future__ import annotations

from chorus.config import (
    CHAT_MODELS,
    IMAGE_MODELS,
)
from chorus.repo.settings import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository):
        self._repo = repo

    def get_image_test_mode(self) -> bool:
        return bool(self._repo.get("image_test_mode", False))

    def set_image_test_mode(self, enabled: bool) -> None:
        self._repo.set("image_test_mode", bool(enabled))

    def get_chat_model(self) -> str:
        return self._repo.get("chat_model") or CHAT_MODELS[0]["model_name"]

    def set_chat_model(self, value: str) -> None:
        self._repo.set("chat_model", value)

    def get_image_model(self) -> str:
        return self._repo.get("image_model") or IMAGE_MODELS[0]["model_name"]

    def set_image_model(self, value: str) -> None:
        self._repo.set("image_model", value)

    def get_web_search(self) -> bool:
        return bool(self._repo.get("web_search", True))

    def set_web_search(self, enabled: bool) -> None:
        self._repo.set("web_search", bool(enabled))
