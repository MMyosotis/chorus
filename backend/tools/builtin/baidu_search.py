"""百度智能搜索工具：对接千帆 ai_search/chat/completions（纯搜索模式）。

用法：把模型字段留空，让百度只返回参考资料（references），不做生成；
本工具把 references 整理成结构化文本喂回 LLM，由 LLM 自己合成回答。
"""

import json
from typing import Optional
from urllib import error as urlerror
from urllib import request as urlrequest

from backend.config import BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL
from backend.tools.base import tool


_RECENCY_VALUES = {"week", "month", "semiyear", "year"}


def _display(args: dict) -> str:
    q = (args.get("query") or "").strip().replace("\n", " ")
    if len(q) > 60:
        q = q[:60] + "…"
    recency = args.get("recency")
    suffix = f" ({recency})" if recency in _RECENCY_VALUES else ""
    return f"百度搜索: {q or '(空查询)'}{suffix}"


def _format_references(refs: list[dict]) -> str:
    """将百度返回的 references 列表格式化为给 LLM 阅读的纯文本。"""
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


@tool(
    name="baidu_search",
    description=(
        "通过百度 AI 搜索接口检索中文互联网信息，返回若干参考资料片段（标题 / URL / 日期 / 摘要）。"
        "当用户问到可能超出训练数据的事实、新闻、知识，或希望给出引用来源时使用。"
        "调用后请基于返回的 references 用中文综合回答，并以 [n] 的形式标注出处编号。"
        "查询应保持简洁；如有需要可使用不同 query 多次调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言搜索查询（建议使用中文），保持具体且简洁。",
            },
            "recency": {
                "type": "string",
                "enum": ["week", "month", "semiyear", "year"],
                "description": "可选的时间范围筛选；不传表示不限时间。",
            },
            "top_k": {
                "type": "integer",
                "description": "拉取的网页参考资料数量上限（1-20，默认 8）。",
                "minimum": 1,
                "maximum": 20,
                "default": 8,
            },
        },
        "required": ["query"],
    },
    display=_display,
    running_label="百度搜索中",
)
def baidu_search(query: str, recency: Optional[str] = None, top_k: int = 8) -> str:
    if not BAIDU_SEARCH_API_KEY:
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
        BAIDU_SEARCH_BASE_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {BAIDU_SEARCH_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return f"Error: Baidu search HTTP {e.code}: {err_body[:500]}"
    except Exception as e:
        return f"Error: Baidu search request failed: {e}"

    if isinstance(data.get("code"), int) and data.get("code") not in (0, 200):
        return f"Error: Baidu search API code={data.get('code')} message={data.get('message')!r}"

    references = data.get("references") or []
    return _format_references(references)
