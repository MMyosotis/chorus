"""任务领域异常：编排或产物有误时抛出，携带修正提示回灌给模型自纠。"""
from __future__ import annotations


class ValidationError(Exception):
    """编排非法或产物有误，附给模型的修正提示。"""

    def __init__(self, message: str, correction: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.correction = correction or message


class AbandonError(Exception):
    """模型主动声明本步无法完成，携带失败说明写入任务 error。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
