"""generate_image 工具：火山方舟 doubao-seedream 图像生成。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from kitty.config import DEFAULT_IMAGE_MODEL_ID
from kitty.tools.base import Tool, ToolContext
from kitty.tools.clients.ark_image import ArkImageClient


@dataclass(frozen=True)
class ImageModelEntry:
    """运行时生图模型条目：HTTP 客户端 + 传给图像 API 的真实 model 名。"""

    client: ArkImageClient
    model_id: str


class GenerateImageTool(Tool):
    name = "generate_image"
    description = (
        "使用火山方舟 Doubao Seedream 模型根据文本提示生成图像。"
        "前端会自动从工具结果渲染图片，因此不要在正文里输出 URL、Markdown 图片（![...]()）"
        "或对图片的描述——用户已经能直接看到图片。"
        "具体使用哪个 Seedream 模型由用户在前端选项栏选定，本工具不接受 model 参数。"
    )
    # parameters 取各 Seedream 模型可接受参数的「并集」：不同模型支持的参数略有差异
    # （如某些尺寸/水印选项），这里只暴露所有模型共同支持的 prompt + size 这一对超集，
    # 使单个工具能服务任意用户选定的模型；模型特有、非通用的参数不进 schema。
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

    def __init__(
        self,
        image_test_mode_fn: Callable[[], bool],
        fake_url: str,
        models: dict[str, ImageModelEntry],
    ):
        self._is_test = image_test_mode_fn
        self._fake_url = fake_url
        self._models = models

    def display(self, arguments: dict) -> str:
        prompt = (arguments.get("prompt") or "").strip().replace("\n", " ")
        if len(prompt) > 60:
            prompt = prompt[:60] + "…"
        return f"生成图像: {prompt or '(空提示词)'}"

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        if self._is_test():
            return self._fake_url
        # ctx.image_model 来自 SettingsService.get_image_model（已校验必在注册表中）或 None（取默认）
        entry = self._models[ctx.image_model or DEFAULT_IMAGE_MODEL_ID]
        return entry.client.generate(
            arguments.get("prompt", ""),
            entry.model_id,
            arguments.get("size", "1024x1024"),
        )
