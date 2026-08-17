"""截断恢复组件：输出超长被截断时放宽预算重发的决策与记账。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from chorus.domain.log import ctx_fields, get_logger

if TYPE_CHECKING:
    from chorus.agents.loop import LoopStrategy
    from chorus.agents.runtime import AgentContext, LoopAction, LoopSignal
    from chorus.domain.stream import StreamResult

_ESCALATED_TOKENS = 64000

_logger = get_logger("loop")


@dataclass
class TruncationGuard:
    """截断恢复组件：放宽预算重发一次的决策与记账，耗尽交策略收尾。"""

    has_escalated: bool = False

    def recover(self, ctx: AgentContext, result: StreamResult, strategy: LoopStrategy) -> Optional["LoopAction"]:
        # 上下文模块反向依赖本组件做默认值，结局信号只能用时再取，避免循环导入
        from chorus.agents.runtime import LoopAction, LoopSignal

        if self.widen_and_retry(result, strategy):
            _logger.info("output truncated, widen budget and resend", extra=ctx_fields(ctx))
            return LoopAction(LoopSignal.CONTINUE, [])
        if result.finish_reason != "length":
            return None
        _logger.warning("output still truncated after widening, give up", extra=ctx_fields(ctx))
        return strategy.on_truncation_exhausted(ctx)

    def widen_and_retry(self, result: StreamResult, strategy: LoopStrategy) -> bool:
        """判定是否放宽预算重发本轮，命中则同时记账改预算。"""
        if self.has_escalated or result.finish_reason != "length":
            return False
        self.has_escalated = True
        strategy.max_tokens = _ESCALATED_TOKENS
        return True
