"""会话标题：清洗归一化规则与生成服务。

清洗剥装饰符并截断；生成服务非流式调模型产出短标题，落库由钩子完成。
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

_GENERATED_MAX_LEN = 30
STORED_TITLE_MAX_LEN = 60

_GENERATED_STRIP_CHARS = "\"'`「」《》 \n\t"


def clean_generated_title(raw: str) -> Optional[str]:
    """清洗生成标题：剥装饰符、去空白、截断；空则返回 None。"""
    title = raw.strip(_GENERATED_STRIP_CHARS)
    if not title:
        return None
    if len(title) > _GENERATED_MAX_LEN:
        title = title[:_GENERATED_MAX_LEN]
    return title


def normalize_title(title: str, max_len: int = STORED_TITLE_MAX_LEN) -> str:
    """归一化标题：去空白并截断。空串保留为空。"""
    title = (title or "").strip()
    if len(title) > max_len:
        title = title[:max_len]
    return title


class TitleGenerationService:
    """非流式一次调用生成短会话标题。仅负责产出文本，落库由钩子完成。"""

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
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
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("title generation failed: %s", e)
            return None
        return clean_generated_title(raw)
