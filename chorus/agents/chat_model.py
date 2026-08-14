"""对话模型提供者：管理各模型的常驻客户端。

初始化时按配置全量构建，读路径无锁天然线程安全。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from chorus.config import CHAT_MODELS, BYPASS_MODEL
from chorus.services.settings import SettingsService


@dataclass(frozen=True)
class ChatModelEntry:
    client: OpenAI
    model_id: str


class ChatModelProvider:
    def __init__(self, settings_service: SettingsService, chat_models: Optional[list[dict]] = None):
        self._settings = settings_service
        self._entries: dict[str, ChatModelEntry] = {
            model["model_name"]: self._build_entry(model)
            for model in (chat_models or CHAT_MODELS)
        }

    @staticmethod
    def _build_entry(model: dict) -> ChatModelEntry:
        api_key = os.environ.get(model["api_key_env"], "")
        return ChatModelEntry(
            client=OpenAI(api_key=api_key, base_url=model["base_url"], max_retries=3),
            model_id=model["model_id"],
        )

    def build_entry(self, model_name: str) -> ChatModelEntry:
        return self._entries[model_name]

    def get_entry(self) -> ChatModelEntry:
        return self.build_entry(self._settings.get_chat_model())

    def bypass_entry(self) -> ChatModelEntry:
        return self.build_entry(BYPASS_MODEL)
