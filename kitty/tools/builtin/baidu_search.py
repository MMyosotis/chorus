"""baidu_search 工具：百度 AI 搜索检索。"""

from __future__ import annotations

from kitty.tools.framework import Tool, ToolContext
from kitty.tools.clients.baidu_search import BaiduSearchClient


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

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        return self._client.search(
            arguments.get("query", ""),
            arguments.get("recency"),
            arguments.get("top_k", 8),
        )
