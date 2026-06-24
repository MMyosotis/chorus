# kitty/domain/task/errors.py
"""任务图领域异常：steps 校验失败 / 产物解析失败共用。

带 correction 字段，供 supervisor 据此喂回模型重试 1 次。
"""
from __future__ import annotations


class ValidationError(Exception):
    """steps 编排非法 / 产物段缺失或字段错。correction 是给模型的修正提示。"""

    def __init__(self, message: str, correction: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.correction = correction or message
