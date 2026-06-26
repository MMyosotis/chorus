"""ImageModelProvider：生图模型客户端的创建与管理。

按 config 条目的 ``provider`` 字段 dispatch 到对应 builder（模块级注册表）。settings 经
SettingsService 查询。初始化时按 config 全量构建所有 entry，读路径无锁。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

from chorus.config import IMAGE_MODELS
from chorus.services.settings import SettingsService
from chorus.tools.clients.ark_image import ArkImageClient


class ImageClient(Protocol):
    def generate(self, prompt: str, model_id: str, size: str) -> str: ...


@dataclass(frozen=True)
class ImageModelEntry:
    client: ImageClient
    model_id: str


def _build_ark(model: dict) -> ImageClient:
    options = model["options"]
    return ArkImageClient(os.environ.get(options["api_key_env"], ""), options["base_url"])


_BUILDERS = {"ark": _build_ark}


class ImageModelProvider:
    def __init__(self, settings_service: SettingsService, image_models: Optional[list[dict]] = None):
        self._settings = settings_service
        self._entries: dict[str, ImageModelEntry] = {
            model["model_name"]: self._build_entry(model)
            for model in (image_models or IMAGE_MODELS)
        }

    @staticmethod
    def _build_entry(model: dict) -> ImageModelEntry:
        builder = _BUILDERS[model["provider"]]
        return ImageModelEntry(client=builder(model), model_id=model["options"]["model_id"])

    def build_entry(self, model_name: str) -> ImageModelEntry:
        return self._entries[model_name]

    def get_entry(self) -> ImageModelEntry:
        return self.build_entry(self._settings.get_image_model())
