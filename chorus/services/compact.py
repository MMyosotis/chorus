"""压缩编排服务：模型现场表的唯一维护者，微压缩换占位、超阈值摘要整段覆写。

原表只存原始事实供前端读，模型只读现场表；服务不持内存状态，重启后从库无损恢复。
"""
from __future__ import annotations

import time
import uuid6
from typing import Optional

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
    """会话模型现场的唯一维护者：微压缩与阈值摘要两级逐层判定。"""

    def __init__(
        self,
        provider_repo: ProviderMessageRepository,
        llm: SummaryGenerationService,
    ):
        self._provider_repo = provider_repo
        self._llm = llm

    def ensure_active(self, session_id: str) -> list[Message]:
        """返回发给模型的现场：先微压缩，估算仍超阈值才摘要覆写。"""
        rows = self._provider_repo.list_by_session(session_id)
        rows = self._micro(session_id, rows)
        # 估算按现场行的实付字数算，换过占位的不再计入
        if estimate_tokens(rows) <= COMPACT_THRESHOLD_TOKENS:
            return rows
        row = self._compact(session_id, rows)
        return [row] if row else rows

    def reactive(self, session_id: str) -> bool:
        """输入超长应急：无视阈值强制摘要，成功则下轮以压缩上下文重试。"""
        rows = self._provider_repo.list_by_session(session_id)
        rows = self._micro(session_id, rows)
        row = self._compact(session_id, rows)
        return row is not None

    def _micro(self, session_id: str, rows: list[Message]) -> list[Message]:
        """内存换占位交给领域纯件，这里只负责把换掉的正文落库。"""
        marked, elided = apply_micro(rows)
        if elided:
            self._provider_repo.elide(session_id, elided, TOOL_PLACEHOLDER)
        return marked

    def _compact(self, session_id: str, rows: list[Message]) -> Optional[UserMessage]:
        """摘要整段覆写现场表，落库后现场只剩一条摘要行。"""
        if not rows:
            return None
        summary = self._llm.summarize(rows)
        if not summary:
            return None
        row = UserMessage(
            id=str(uuid6.uuid7()), session_id=session_id,
            created_at=time.time(), content=f"[历史压缩摘要]\n{summary}",
        )
        self._provider_repo.replace_with_summary(session_id, row)
        _logger.info("history compacted", extra={
            "session_id": session_id, "covered": len(rows), "summary_chars": len(summary),
        })
        return row
