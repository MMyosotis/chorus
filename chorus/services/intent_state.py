"""意图状态服务：主 Agent 工作记忆的读写与确认门禁。"""

from __future__ import annotations

import time
from typing import Iterable

from chorus.domain.events import IntentStateEvent
from chorus.domain.intent import IntentState, IntentStateUpdate
from chorus.repo.intent_state import IntentStateRepository
from chorus.services.session import SessionService


_EVENT_TOOL_NAMES = {"update_intent_state"}


class IntentStateService:
    def __init__(
        self,
        repo: IntentStateRepository,
        session_service: SessionService,
    ):
        self._repo = repo
        self._session = session_service

    def get(self, session_id: str) -> IntentState:
        state = self._repo.get(session_id)
        # 配图数量无默认值,新会话初始空状态用 0 占位表示尚未向用户确认。
        return state if state is not None else IntentState(session_id=session_id, image_count=0)

    def update_from_tool(self, session_id: str, update: IntentStateUpdate) -> IntentState:
        current = self.get(session_id)
        state = IntentState.from_update(update, session_id=session_id, version=current.version + 1)
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def mark_dispatched(self, session_id: str) -> IntentState:
        return self.patch_status(session_id, "dispatched")

    def is_confirmed(self, session_id: str) -> bool:
        return self.get(session_id).intent_status == "confirmed"

    def patch_status(self, session_id: str, status: str) -> IntentState:
        current = self.get(session_id)
        state = current.model_copy(
            update={
                "intent_status": status,
                "version": current.version + 1,
                "updated_at": time.time(),
            }
        )
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def events_for_turn(
        self, session_id: str, tool_names: Iterable[str],
    ) -> list[IntentStateEvent]:
        """生成本轮意图工具完成后应推送的状态事件。"""
        events = []
        for tool_name in tool_names:
            if tool_name not in _EVENT_TOOL_NAMES:
                continue
            events.append(IntentStateEvent(state=self.get(session_id)))
        return events
