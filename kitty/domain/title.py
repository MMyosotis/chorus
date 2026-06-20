"""会话标题领域规则：清洗与归一化。

两类语义不同的处理：
- clean_generated_title：LLM 原始输出的清洗（剥引号/书名号 + 截 30 字 + 空判）。
  阈值 30 是对模型原始输出的安全截断。
- normalize_title：用户手改 / 自动生成标题的归一化（strip + 截 max_len）。
  阈值 60 是入库标题的字段上限，较宽松。

纯领域：输入字符串、输出字符串，零基础设施依赖。
"""

from __future__ import annotations

from typing import Optional

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
