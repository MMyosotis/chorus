"""火山方舟图像生成客户端，只负责真实接口调用，测试模式短路在工具层。"""

from __future__ import annotations

import json
from urllib import error as urlerror
from urllib import request as urlrequest


class ArkImageClient:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url

    def generate(self, prompt: str, model_id: str, size: str) -> str:
        payload = {
            "model": model_id,
            "prompt": prompt,
            "size": size,
            "response_format": "url",
            "watermark": False,
        }
        req = urlrequest.Request(
            self._base_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlrequest.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            return f"Error: 图像服务返回 HTTP {e.code}"
        except Exception as e:
            return f"Error: 图像请求失败: {type(e).__name__}"

        items = data.get("data") or []
        img_url = items[0].get("url") if items else ""
        return img_url or "Error: 图像服务未返回图片"
