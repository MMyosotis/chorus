"""AssistantTextResponse hook（done 之后）：生成短标题并 yield title_update。

注册顺序排在 text_response 之后。前端在收到 done 时已经解锁，title_update 是补丁式后续事件。
"""

from typing import Optional

from backend.config import MODEL_ID
from backend.hooks.manager import AgentContext


def _maybe_generate_title(client, conv: dict) -> Optional[str]:
    if conv.get("title_generated"):
        return None
    history = conv.get("history", [])
    first_user = None
    first_assistant = None
    for m in history:
        if first_user is None and m.get("role") == "user":
            first_user = m.get("content") or ""
        if (
            first_assistant is None
            and m.get("role") == "assistant"
            and (m.get("content") or "").strip()
        ):
            first_assistant = m.get("content") or ""
        if first_user and first_assistant:
            break
    if not first_user or not first_assistant:
        return None
    user_part = first_user[:200]
    assistant_part = first_assistant[:200]
    prompt = (
        "请基于以下对话生成一个 5–12 字的中文标题，仅返回标题文本，不要标点和引号。\n\n"
        f"用户：{user_part}\n助手：{assistant_part}"
    )
    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=32,
            stream=False,
        )
        title = (resp.choices[0].message.content or "").strip()
        title = title.strip("\"'`「」《》 \n\t")
        if not title:
            return None
        if len(title) > 30:
            title = title[:30]
        return title
    except Exception:
        return None


def make_title_hook(client):
    """工厂：把 OpenAI client 注入 closure，避免硬依赖 chat 模块全局。"""

    def on_title(ctx: AgentContext):
        title = _maybe_generate_title(client, ctx.conv)
        if not title:
            return None
        if not ctx.store.set_title_if_unset(ctx.conversation_id, title):
            return None
        return [{
            "type": "title_update",
            "id": ctx.conversation_id,
            "title": title,
        }]

    return on_title
