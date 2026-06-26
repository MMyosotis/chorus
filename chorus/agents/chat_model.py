"""ChatModelProvider：对话模型 ChatModelEntry 的创建与管理。

消费者是 supervisor/subagent（agents/），provider 与消费者同层。chat 各家都是 OpenAI 兼容
协议，单 builder 够用。初始化时按 config 全量构建所有 entry（每模型一个常驻客户端），读路径
无锁、天然线程安全。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from chorus.config import CHAT_MODELS, TITLE_MODEL
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

    def title_entry(self) -> ChatModelEntry:
        return self.build_entry(TITLE_MODEL)
