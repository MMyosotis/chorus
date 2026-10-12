"""压缩编排：supervisor 现场表压缩与 subagent 内存历史压缩的唯一入口。

原表只存原始事实供前端读，模型只读现场表；服务不持内存状态，重启后从库无损恢复。
"""
from __future__ import annotations

import time
import uuid6
from typing import Callable, Optional

from chorus.domain.bypass import BypassScope
from chorus.domain.compact import (
    COMPACT_THRESHOLD_TOKENS,
    TOOL_PLACEHOLDER,
    SummaryGenerationService,
    apply_micro,
    estimate_tokens,
)
from chorus.domain.log import get_logger
from chorus.domain.message import Message, UserMessage
from chorus.repo.provider_message import ProviderMessageRepository

_logger = get_logger("service.compact")


class CompactService:
    """压缩统一入口：supervisor 现场表两级压缩与 subagent 内存历史微压缩共用一条管线。"""

    def __init__(
        self,
        provider_repo: ProviderMessageRepository,
        llm: SummaryGenerationService,
    ):
        self._provider_repo = provider_repo
        self._llm = llm

    def compact_history(self, messages: list[Message]) -> list[Message]:
        """内存历史压缩门（subagent 用）：同一条管线，只到微压缩为止，无摘要级。"""
        marked, _ = self._pipeline(messages)
        return marked

    def ensure_active(self, session_id: str) -> list[Message]:
        """返回发给模型的现场：进管线挂摘要兜底级，换掉的正文落库。"""
        rows = self._provider_repo.list_by_session(session_id)
        marked, elided = self._pipeline(rows, still_overflow=lambda msgs: self._compact(session_id, msgs))
        if elided:
            self._provider_repo.elide(session_id, elided, TOOL_PLACEHOLDER)
        return marked

    def reactive(self, session_id: str) -> bool:
        """输入超长应急门：无视阈值强制微压缩加摘要，成功则下轮以压缩上下文重试。"""
        rows = self._provider_repo.list_by_session(session_id)
        rows = self._micro(session_id, rows)
        return bool(self._compact(session_id, rows))

    def _pipeline(
        self,
        messages: list[Message],
        still_overflow: Optional[Callable[[list[Message]], list[Message]]] = None,
    ) -> tuple[list[Message], list[str]]:
        """统一管线：没超阈值原样返回，超了先微压缩，压完仍超才交兜底级。"""
        if estimate_tokens(messages) <= COMPACT_THRESHOLD_TOKENS:
            return messages, []
        marked, elided = apply_micro(messages)
        if still_overflow is not None and estimate_tokens(marked) > COMPACT_THRESHOLD_TOKENS:
            marked = still_overflow(marked)
        return marked, elided

    def _micro(self, session_id: str, rows: list[Message]) -> list[Message]:
        """内存换占位交给领域纯件，这里只负责把换掉的正文落库。"""
        marked, elided = apply_micro(rows)
        if elided:
            self._provider_repo.elide(session_id, elided, TOOL_PLACEHOLDER)
        return marked

    def _compact(self, session_id: str, rows: list[Message]) -> list[Message]:
        """摘要整段覆写现场表，落库后现场只剩一条摘要行；摘要失败维持原行。"""
        if not rows:
            return rows
        summary = self._llm.summarize(rows, BypassScope(session_id=session_id))
        if not summary:
            return rows
        row = UserMessage(
            id=str(uuid6.uuid7()), session_id=session_id,
            created_at=time.time(), content=f"[历史压缩摘要]\n{summary}",
        )
        self._provider_repo.replace_with_summary(session_id, row)
        _logger.info("history compacted", extra={
            "session_id": session_id, "covered": len(rows), "summary_chars": len(summary),
        })
        return [row]
