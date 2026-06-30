"""generate_image 工具：火山方舟 doubao-seedream 图像生成。

含本工具的生图模型 provider——按 config 条目的 ``provider`` 字段 dispatch 到对应 builder
（模块级注册表），settings 经 SettingsService 查询。初始化时按 config 全量构建所有 entry，
读路径无锁。当前仅 ark 一种 provider。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

from chorus.config import IMAGE_MODELS
from chorus.services.settings import SettingsService
from chorus.tools.clients.ark_image import ArkImageClient
from chorus.tools.framework import Reply, Tool, ToolContext, ToolRunResult

# 测试模式短路返回的固定 URL（不调真实 API，验证全链路渲染用）。
_FAKE_URL = "https://gips2.baidu.com/it/u=195724436,3554684702&fm=3028&app=3028&f=JPEG&fmt=auto?w=1280&h=960"


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


class GenerateImageTool(Tool):
    name = "generate_image"
    description = (
        "使用火山方舟 Doubao Seedream 模型根据文本提示生成图像。"
        "前端会自动从工具结果渲染图片，因此不要在正文里输出 URL、Markdown 图片（![...]()）"
        "或对图片的描述——用户已经能直接看到图片。"
        "具体使用哪个 Seedream 模型由用户在前端选项栏选定，本工具不接受 model 参数。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图像描述（中英文均可）。需明确说明主体、风格、光线、构图等关键要素。",
            },
            "size": {
                "type": "string",
                "description": "图像尺寸，如 '1024x1024'、'2048x2048'、'1024x1792'。默认 1024x1024。",
                "default": "1024x1024",
            },
        },
        "required": ["prompt"],
    }
    running_label = "图片生成中"

    def __init__(self, settings_service: SettingsService, provider: ImageModelProvider):
        self._settings = settings_service
        self._provider = provider

    def display(self, arguments: dict) -> str:
        prompt = (arguments.get("prompt") or "").strip().replace("\n", " ")
        if len(prompt) > 60:
            prompt = prompt[:60] + "…"
        return f"生成图像: {prompt or '(空提示词)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        if self._settings.get_image_test_mode():
            return ToolRunResult(Reply(_FAKE_URL), activity_meta={"url": _FAKE_URL})
        entry = self._provider.get_entry()
        url = entry.client.generate(
            arguments.get("prompt", ""),
            entry.model_id,
            arguments.get("size", "1024x1024"),
        )
        return ToolRunResult(Reply(url), activity_meta={"url": url})
