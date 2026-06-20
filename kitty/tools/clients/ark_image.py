"""ArkImageClient：火山方舟 doubao-seedream 图像生成 HTTP 客户端。

把原 generate_image 工具里的 urllib 调用抽出为独立对象，由 create_app() 注入。
test 模式的短路返回在 Tool 层判断，本类只负责真实 API 调用。
"""

from __future__ import annotations

import json
from urllib import error as urlerror
from urllib import request as urlrequest


class ArkImageClient:
    def __init__(self, api_key: str, base_url: str, models: dict[str, str]):
        self._api_key = api_key
        self._base_url = base_url
        self._models = models

    def generate(self, prompt: str, model: str, size: str) -> str:
        if not self._api_key:
            return "Error: ARK_IMAGE_API_KEY 未配置，无法调用图像生成 API"
        real_model = self._models.get(model)
        if not real_model:
            return f"Error: unknown model '{model}'. Available: {list(self._models.keys())}"

        payload = {
            "model": real_model,
            "prompt": prompt,
            "size": size,
            "response_format": "url",
            "watermark": False,
        }
        body = json.dumps(payload).encode("utf-8")
        url = f"{self._base_url.rstrip('/')}/images/generations"
        req = urlrequest.Request(
            url, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            return self._http_error(e)
        except Exception as e:
            return f"Error: image API request failed: {e}"

        items = data.get("data") or []
        if not items:
            return f"Error: image API returned no data: {json.dumps(data, ensure_ascii=False)[:500]}"
        img_url = items[0].get("url")
        if not img_url:
            return f"Error: image API returned no url: {json.dumps(items[0], ensure_ascii=False)[:500]}"
        return img_url

    @staticmethod
    def _http_error(e: urlerror.HTTPError) -> str:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return f"Error: image API HTTP {e.code}: {err_body[:500]}"
