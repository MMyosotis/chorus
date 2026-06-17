"""TitleGenerationService：非流式一次调用生成 5-12 字会话标题。

被 TitleHook 注入，首轮 assistant 文本回复后调用。仅负责"生成标题文本"，
落库（set_title_if_unset）由 hook 经 SessionService 完成。
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class TitleGenerationService:
    def __init__(self, openai_client: OpenAI, model_id: str):
        self._client = openai_client
        self._model = model_id

    def generate(self, first_user: str, first_assistant: str) -> Optional[str]:
        if not first_user or not first_assistant:
            return None
        prompt = (
            "请基于以下对话生成一个 5–12 字的中文标题，仅返回标题文本，不要标点和引号。\n\n"
            f"用户：{first_user[:200]}\n助手：{first_assistant[:200]}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=32,
                stream=False,
            )
            title = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("title generation failed: %s", e)
            return None
        return self._clean(title)

    @staticmethod
    def _clean(title: str) -> Optional[str]:
        title = title.strip("\"'`「」《》 \n\t")
        if not title:
            return None
        if len(title) > 30:
            title = title[:30]
        return title
