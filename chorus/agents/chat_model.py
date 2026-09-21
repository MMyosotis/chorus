"""对话模型提供者：管理各模型的常驻客户端。

初始化时按配置全量构建，读路径无锁天然线程安全。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from pydantic import BaseModel, ConfigDict

from chorus.config import CHAT_MODELS, BYPASS_MODEL, ChatModelConfig
from chorus.domain.trace import ModelUsage
from chorus.services.settings import SettingsService


class ModelPricing(BaseModel):
    """模型计价：入出单价按元 / 百万 token 记，对一次用量折算费用。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_price: float
    output_price: float

    def cost_cny(self, usage: Optional[ModelUsage]) -> Optional[float]:
        if usage is None:
            return None
        tokens_cny = usage.input_tokens * self.input_price + usage.output_tokens * self.output_price
        return round(tokens_cny / 1_000_000, 4)


@dataclass(frozen=True)
class ChatModelEntry:
    client: OpenAI
    model_id: str
    pricing: Optional[ModelPricing] = None


class ChatModelProvider:
    def __init__(self, settings_service: SettingsService, chat_models: list[ChatModelConfig]):
        self._settings = settings_service
        self._entries: dict[str, ChatModelEntry] = {
            model.model_name: self._build_entry(model) for model in chat_models
        }

    @staticmethod
    def _build_entry(model: ChatModelConfig) -> ChatModelEntry:
        api_key = os.environ.get(model.api_key_env, "")
        return ChatModelEntry(
            client=OpenAI(api_key=api_key, base_url=model.base_url, max_retries=3),
            model_id=model.model_id,
            pricing=ChatModelProvider._build_pricing(model),
        )

    @staticmethod
    def _build_pricing(model: ChatModelConfig) -> Optional[ModelPricing]:
        """入出两个单价都配置才计价，缺一按未配置处理。"""
        if model.input_price is None or model.output_price is None:
            return None
        return ModelPricing(input_price=model.input_price, output_price=model.output_price)

    def build_entry(self, model_name: str) -> ChatModelEntry:
        return self._entries[model_name]

    def get_entry(self) -> ChatModelEntry:
        return self.build_entry(self._settings.get_chat_model())

    def bypass_entry(self) -> ChatModelEntry:
        return self.build_entry(BYPASS_MODEL)
