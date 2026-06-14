"""图像生成工具：接入火山方舟 doubao-seedream 系列。"""

import json
from urllib import error as urlerror
from urllib import request as urlrequest

from backend.config import (
    ARK_IMAGE_API_KEY,
    ARK_IMAGE_BASE_URL,
    ARK_IMAGE_MODELS,
    IMAGE_TEST_FAKE_URL,
    IMAGE_TEST_MODE,
)
from backend.tools.base import tool


def _display(args: dict) -> str:
    model = args.get("model") or "seedream-4"
    prompt = (args.get("prompt") or "").strip().replace("\n", " ")
    if len(prompt) > 60:
        prompt = prompt[:60] + "…"
    return f"生成图像 [{model}]: {prompt or '(空提示词)'}"


@tool(
    name="generate_image",
    description=(
        "使用火山方舟 Doubao Seedream 模型根据文本提示生成图像。"
        "前端会自动从工具结果渲染图片，因此不要在正文里输出 URL、Markdown 图片（![...]()）"
        "或对图片的描述——用户已经能直接看到图片。"
        "可选模型：'seedream-4'（质量更高、速度较慢）、'seedream-5-lite'（更快、更便宜）。"
    ),
    parameters={
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
    },
    display=_display,
    running_label="图片生成中",
)
def generate_image(prompt: str, model: str = "seedream-4", size: str = "1024x1024") -> str:
    if IMAGE_TEST_MODE:
        return IMAGE_TEST_FAKE_URL

    if not ARK_IMAGE_API_KEY:
        return "Error: ARK_IMAGE_API_KEY 未配置，无法调用图像生成 API"

    real_model = ARK_IMAGE_MODELS.get(model)
    if not real_model:
        return f"Error: unknown model '{model}'. Available: {list(ARK_IMAGE_MODELS.keys())}"

    payload = {
        "model": real_model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"{ARK_IMAGE_BASE_URL.rstrip('/')}/images/generations"
    req = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {ARK_IMAGE_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlrequest.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return f"Error: image API HTTP {e.code}: {err_body[:500]}"
    except Exception as e:
        return f"Error: image API request failed: {e}"

    items = data.get("data") or []
    if not items:
        return f"Error: image API returned no data: {json.dumps(data, ensure_ascii=False)[:500]}"

    img_url = items[0].get("url")
    if not img_url:
        return f"Error: image API returned no url: {json.dumps(items[0], ensure_ascii=False)[:500]}"

    # 直接返回 URL（不带 Markdown）。前端识别 generate_image 工具后自行渲染图片，
    # 由 prompt（见 description）确保模型不会把 URL 复述到正文。
    return img_url
