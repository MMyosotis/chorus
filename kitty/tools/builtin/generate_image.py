"""generate_image 工具：火山方舟 doubao-seedream 图像生成。"""

from __future__ import annotations

from typing import Callable

from kitty.tools.base import Tool, ToolContext
from kitty.tools.clients.ark_image import ArkImageClient


class GenerateImageTool(Tool):
    name = "generate_image"
    description = (
        "使用火山方舟 Doubao Seedream 模型根据文本提示生成图像。"
        "前端会自动从工具结果渲染图片，因此不要在正文里输出 URL、Markdown 图片（![...]()）"
        "或对图片的描述——用户已经能直接看到图片。"
        "可选模型：'seedream-4'（质量更高、速度较慢）、'seedream-5-lite'（更快、更便宜）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图像描述（中英文均可）。需明确说明主体、风格、光线、构图等关键要素。",
            },
            "model": {
                "type": "string",
                "enum": ["seedream-4", "seedream-5-lite"],
                "description": (
                    "使用的 Doubao 模型。"
                    "'seedream-4' = doubao-seedream-4.0（质量更高、速度较慢）；"
                    "'seedream-5-lite' = doubao-seedream-5.0-lite-new（更快、更便宜）。"
                ),
                "default": "seedream-4",
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

    def __init__(self, image_test_mode_fn: Callable[[], bool], fake_url: str, client: ArkImageClient):
        self._is_test = image_test_mode_fn
        self._fake_url = fake_url
        self._client = client

    def display(self, arguments: dict) -> str:
        model = arguments.get("model") or "seedream-4"
        prompt = (arguments.get("prompt") or "").strip().replace("\n", " ")
        if len(prompt) > 60:
            prompt = prompt[:60] + "…"
        return f"生成图像 [{model}]: {prompt or '(空提示词)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        if self._is_test():
            return self._fake_url
        return self._client.generate(
            arguments.get("prompt", ""),
            arguments.get("model", "seedream-4"),
            arguments.get("size", "1024x1024"),
        )
