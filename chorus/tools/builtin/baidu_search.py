"""baidu_search 工具：百度 AI 搜索检索。

参数规整（query strip / top_k clamp）与 references 渲染在本 Tool 层，
client 只负责真实 API 调用（成功返原始 list[dict]，失败返错误 str）。
"""

from __future__ import annotations

from chorus.tools.framework import Reply, Tool, ToolContext
from chorus.tools.clients.baidu_search import BaiduSearchClient


def _format_references(refs: list[dict]) -> str:
    if not refs:
        return "(没有找到相关搜索结果)"
    lines: list[str] = []
    for i, ref in enumerate(refs, 1):
        title = (ref.get("title") or "").strip() or "(无标题)"
        url = (ref.get("url") or "").strip()
        date = (ref.get("date") or "").strip()
        anchor = (ref.get("web_anchor") or "").strip()
        content = (ref.get("content") or "").strip().replace("\n", " ")
        if len(content) > 400:
            content = content[:400] + "…"
        meta_parts = [p for p in (anchor, date) if p]
        meta = f"  ({' · '.join(meta_parts)})" if meta_parts else ""
        lines.append(f"[{i}] {title}{meta}\n    URL: {url}\n    摘要: {content or '(无摘要)'}")
    return "\n".join(lines)


class BaiduSearchTool(Tool):
    name = "baidu_search"
    description = (
        "通过百度 AI 搜索接口检索中文互联网信息，返回若干参考资料片段（标题 / URL / 日期 / 摘要）。"
        "当用户问到可能超出训练数据的事实、新闻、知识，或希望给出引用来源时使用。"
        "调用后请基于返回的 references 用中文综合回答，并以 [n] 的形式标注出处编号。"
        "查询应保持简洁；如有需要可使用不同 query 多次调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "自然语言搜索查询（建议使用中文），保持具体且简洁。"},
            "recency": {
                "type": "string",
                "enum": ["week", "month", "semiyear", "year"],
                "description": "可选的时间范围筛选；不传表示不限时间。",
            },
            "top_k": {
                "type": "integer",
                "description": "拉取的网页参考资料数量上限（1-20，默认 8）。",
                "minimum": 1, "maximum": 20, "default": 8,
            },
        },
        "required": ["query"],
    }
    running_label = "百度搜索中"

    def __init__(self, client: BaiduSearchClient):
        self._client = client

    def display(self, arguments: dict) -> str:
        q = (arguments.get("query") or "").strip().replace("\n", " ")
        if len(q) > 60:
            q = q[:60] + "…"
        recency = arguments.get("recency")
        suffix = f" ({recency})" if recency in {"week", "month", "semiyear", "year"} else ""
        return f"百度搜索: {q or '(空查询)'}{suffix}"

    def run(self, arguments: dict, ctx: ToolContext) -> Reply:
        query = (arguments.get("query") or "").strip()
        if not query:
            return Reply("Error: query 不能为空")
        try:
            top_k = max(1, min(20, int(arguments.get("top_k", 8))))
        except (TypeError, ValueError):
            top_k = 8

        result = self._client.search(query, arguments.get("recency"), top_k)
        return Reply(result if isinstance(result, str) else _format_references(result))
