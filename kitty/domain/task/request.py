# kitty/domain/task/request.py
"""create_plan 工具成功时的建图载荷。

只含建图必需数据（intent + steps），不含沟通话术、不含产物。friendly_reply 是
supervisor 对用户的话（沟通出口），由 supervisor 从原始 call.arguments 取，不进载荷。
"""
from __future__ import annotations

from dataclasses import dataclass

from kitty.domain.task.models import CreationIntent, StepSpec


@dataclass(frozen=True)
class PlanRequest:
    """建图载荷：解析+校验通过的 intent 与 steps，供 supervisor 落库建图。"""
    intent: CreationIntent
    steps: list[StepSpec]
