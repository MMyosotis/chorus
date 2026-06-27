"""千帆 ai_search 检索客户端（纯搜索模式）。

参数规整与结果渲染在 Tool 层，本类只负责真实 API 调用。成功返原始 references，
失败返错误文本（str），由 Tool 用 isinstance 区分。
"""

from __future__ import annotations

import json
from typing import Optional, Union
from urllib import error as urlerror
from urllib import request as urlrequest

_RECENCY_VALUES = {"week", "month", "semiyear", "year"}


class BaiduSearchClient:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url

    def search(self, query: str, recency: Optional[str], top_k: int) -> Union[list[dict], str]:
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
            return f"Error: 百度搜索服务返回 HTTP {e.code}"
        except Exception as e:
            return f"Error: 百度搜索请求失败: {type(e).__name__}"

        code = data.get("code")
        if isinstance(code, int) and code not in (0, 200):
            return f"Error: 百度搜索返回业务错误 code={code}"
        return data.get("references") or []
