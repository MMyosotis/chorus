"""千帆 ai_search 检索客户端（纯搜索模式）。"""

from __future__ import annotations

import json
from typing import Optional
from urllib import error as urlerror
from urllib import request as urlrequest

_RECENCY_VALUES = {"week", "month", "semiyear", "year"}


class BaiduSearchClient:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url

    def search(self, query: str, recency: Optional[str], top_k: int) -> str:
        if not self._api_key:
            return "Error: BAIDU_SEARCH_API_KEY 未配置，无法调用百度搜索 API"
        query = (query or "").strip()
        if not query:
            return "Error: query 不能为空"
        try:
            top_k_int = max(1, min(20, int(top_k)))
        except (TypeError, ValueError):
            top_k_int = 8

        payload: dict = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": top_k_int}],
            "stream": False,
        }
        if recency in _RECENCY_VALUES:
            payload["search_recency_filter"] = recency

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urlrequest.Request(
            self._base_url, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urlerror.HTTPError as e:
            return self._http_error(e)
        except Exception as e:
            return f"Error: Baidu search request failed: {e}"

        if isinstance(data.get("code"), int) and data.get("code") not in (0, 200):
            return f"Error: Baidu search API code={data.get('code')} message={data.get('message')!r}"
        return self._format_references(data.get("references") or [])

    @staticmethod
    def _http_error(e: urlerror.HTTPError) -> str:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return f"Error: Baidu search HTTP {e.code}: {err_body[:500]}"

    @staticmethod
    def _format_references(refs: list[dict]) -> str:
        if not refs:
            return "(没有找到相关搜索结果)"
        lines: list[str] = []
        for i, r in enumerate(refs, 1):
            title = (r.get("title") or "").strip() or "(无标题)"
            url = (r.get("url") or "").strip()
            date = (r.get("date") or "").strip()
            anchor = (r.get("web_anchor") or "").strip()
            content = (r.get("content") or "").strip().replace("\n", " ")
            if len(content) > 400:
                content = content[:400] + "…"
            meta_parts = [p for p in (anchor, date) if p]
            meta = f"  ({' · '.join(meta_parts)})" if meta_parts else ""
            lines.append(f"[{i}] {title}{meta}\n    URL: {url}\n    摘要: {content or '(无摘要)'}")
        return "\n".join(lines)
