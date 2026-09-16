"""旁路 LLM 调用:agent loop 之外的非流式单轮调用,关闭思考避免推理段吃光预算。

调完连请求带响应落一行轨迹,轨迹失败不阻断调用本身。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

from chorus.domain.log import get_logger
from chorus.domain.trace import BypassCall, ModelUsage, TraceEntry, TracePhase

_logger = get_logger("domain.bypass")

_NO_THINKING = {"thinking": {"type": "disabled"}}


@dataclass(frozen=True)
class BypassScope:
    """一次旁路调用的归属:会话必填,任务与发起方由调用点按实际情况带。"""

    session_id: str
    task_id: Optional[str] = None
    source: str = "supervisor"


class BypassCaller:
    """非流式单轮调用并落轨迹,返回去空白后的完整正文,异常上抛交调用方兜底。"""

    def __init__(
        self,
        client: OpenAI,
        model_id: str,
        sink: Callable[[TraceEntry], None],
        cost_fn: Optional[Callable[[ModelUsage], Optional[float]]] = None,
    ):
        self._client = client
        self._model = model_id
        self._sink = sink
        self._cost_fn = cost_fn

    def call(self, prompt: str, max_tokens: int, purpose: str, scope: BypassScope) -> str:
        started = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[ChatCompletionUserMessageParam(role="user", content=prompt)],
                max_tokens=max_tokens,
                stream=False,
                extra_body=_NO_THINKING,
            )
        except Exception as exc:
            self._record(prompt, max_tokens, purpose, scope, duration_ms=self._elapsed(started), error=str(exc))
            raise
        content = (resp.choices[0].message.content or "").strip()
        self._record(
            prompt, max_tokens, purpose, scope,
            duration_ms=self._elapsed(started), usage=self._usage(resp), content=content,
        )
        return content

    @staticmethod
    def _elapsed(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _usage(resp) -> Optional[ModelUsage]:
        usage = resp.usage
        if usage is None:
            return None
        return ModelUsage(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    def _record(
        self, prompt: str, max_tokens: int, purpose: str, scope: BypassScope,
        *, duration_ms: int, content: str = "",
        usage: Optional[ModelUsage] = None, error: Optional[str] = None,
    ) -> None:
        payload = BypassCall(
            purpose=purpose, model=self._model, prompt=prompt, max_tokens=max_tokens,
            content=content, status="error" if error else "success",
            duration_ms=duration_ms, usage=usage,
            cost_cny=self._cost_fn(usage) if self._cost_fn and usage else None,
            error=error,
        )
        entry = TraceEntry(
            id=None, session_id=scope.session_id, message_id=None, task_id=scope.task_id,
            source=scope.source, phase=TracePhase.BYPASS_CALL, created_at=time.time(),
            payload=payload,
        )
        try:
            self._sink(entry)
        except Exception:
            _logger.exception("bypass trace record failed")
