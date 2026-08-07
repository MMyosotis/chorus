"""会话标题：清洗归一化规则与生成服务。

清洗剥装饰符并截断；生成服务非流式调模型产出短标题，落库由钩子完成。
"""

from __future__ import annotations

from typing import Optional

from openai import OpenAI

from chorus.domain.bypass import call_once

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

    def generate(self, user_text: str) -> Optional[str]:
        if not user_text:
            return None
        prompt = (
            "请基于以下用户消息生成一个 5–12 字的中文标题，仅返回标题文本，不要标点和引号。\n\n"
            f"用户：{user_text[:200]}"
        )
        try:
            # 推理模型先吐推理段再作答，预算须覆盖推理段
            raw = call_once(self._client, self._model, prompt, 512)
        except Exception:
            return None
        return clean_generated_title(raw)
