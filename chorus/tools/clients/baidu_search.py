"""百度搜索客户端，只负责真实接口调用；失败抛专用异常由工具层转写回执。"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel
from urllib import error as urlerror
from urllib import request as urlrequest

_RECENCY_VALUES = {"week", "month", "semiyear", "year"}


class SearchRef(BaseModel):
    """百度搜索返回的单条网页参考资料。"""

    title: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    web_anchor: Optional[str] = None
    content: Optional[str] = None


class BaiduSearchError(Exception):
    """百度搜索接口调用失败。"""


class BaiduSearchClient:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url

    def search(self, query: str, recency: Optional[str], top_k: int) -> list[SearchRef]:
        payload: dict = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": top_k}],
            "stream": False,
        }
        if recency in _RECENCY_VALUES:
            payload["search_recency_filter"] = recency

        req = urlrequest.Request(
            self._base_url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlrequest.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            raise BaiduSearchError(f"百度搜索服务返回 HTTP {e.code}") from e
        except Exception as e:
            raise BaiduSearchError(f"百度搜索请求失败: {type(e).__name__}") from e

        code = data.get("code")
        if isinstance(code, int) and code not in (0, 200):
            raise BaiduSearchError(f"百度搜索返回业务错误 code={code}")
        return [SearchRef.model_validate(item) for item in (data.get("references") or [])]
