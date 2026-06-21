"""会话标题领域规则：清洗与归一化 + 标题生成服务。

clean_generated_title 清洗 LLM 原始输出（剥引号/书名号 + 截 30 字）；
normalize_title 归一化入库标题（strip + 截 60 字）。
TitleGenerationService 非流式一次调用生成 5-12 字标题，落库由 TitleHook 经 SessionService 完成。
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# LLM 原始标题的安全截断阈值
_GENERATED_MAX_LEN = 30
# 入库标题字段上限（用户手改 / 自动生成共用）
STORED_TITLE_MAX_LEN = 60

_GENERATED_STRIP_CHARS = "\"'`「」《》 \n\t"


def clean_generated_title(raw: str) -> Optional[str]:
    """清洗 LLM 生成的原始标题：剥引号/书名号、strip、截 30 字；空则返回 None。"""
    title = raw.strip(_GENERATED_STRIP_CHARS)
    if not title:
        return None
    if len(title) > _GENERATED_MAX_LEN:
        title = title[:_GENERATED_MAX_LEN]
    return title


def normalize_title(title: str, max_len: int = STORED_TITLE_MAX_LEN) -> str:
    """归一化标题：strip + 截 max_len。空串保留为空（是否拒绝由调用方决策）。"""
    title = (title or "").strip()
    if len(title) > max_len:
        title = title[:max_len]
    return title


class TitleGenerationService:
    """非流式一次调用生成 5-12 字会话标题。

    被 TitleHook 注入，首轮 assistant 文本回复后调用。仅负责生成标题文本
    （调 OpenAI + 清洗），落库由 hook 经 SessionService 完成。
    """

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
