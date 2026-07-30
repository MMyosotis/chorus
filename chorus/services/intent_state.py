"""意图状态服务：主 Agent 工作记忆的读写与确认门禁。"""

from __future__ import annotations

import time
from typing import Iterable, Optional

import uuid6

from chorus.domain.events import IntentStateEvent
from chorus.domain.intent import (
    IntentConfirmation,
    IntentConfirmationAnswer,
    IntentSnapshot,
    IntentState,
    IntentStateUpdate,
)
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.services.session import SessionService


_EVENT_TOOL_NAMES = {"update_intent_state"}


class IntentStateService:
    def __init__(
        self,
        repo: IntentStateRepository,
        confirmation_repo: IntentConfirmationRepository,
        session_service: SessionService,
    ):
        self._repo = repo
        self._confirmation_repo = confirmation_repo
        self._session = session_service

    def get(self, session_id: str) -> IntentState:
        state = self._repo.get(session_id)
        # 配图数量无默认值,新会话初始空状态用 0 占位表示尚未向用户确认。
        return state if state is not None else IntentState(session_id=session_id, image_count=0)

    def update_from_tool(self, session_id: str, update: IntentStateUpdate) -> IntentState:
        current = self.get(session_id)
        state = IntentState(
            session_id=session_id,
            **update.model_dump(),
            version=current.version + 1,
            updated_at=time.time(),
        )
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

    def open_confirmation(
        self, session_id: str, snapshot: IntentSnapshot, message_id: Optional[str] = None,
    ) -> IntentConfirmation:
        """待确认时固化一份意图快照留档，供作答后留痕。"""
        fields = snapshot.model_dump(include=set(IntentSnapshot.model_fields))
        confirmation = IntentConfirmation(
            confirmation_id=str(uuid6.uuid7()),
            session_id=session_id,
            message_id=message_id,
            **fields,
        )
        self._confirmation_repo.insert(confirmation)
        self._session.touch(session_id)
        return confirmation

    def mark_confirmation_answered(self, session_id: str, answer: IntentConfirmationAnswer) -> None:
        self._confirmation_repo.update_answered(session_id, answer)
        self._session.touch(session_id)

    def list_confirmations(self, session_id: str) -> list[IntentConfirmation]:
        return self._confirmation_repo.find_by_session(session_id)

    def get_open_confirmation(self, session_id: str) -> Optional[IntentConfirmation]:
        return self._confirmation_repo.find_open_by_session(session_id)

    def events_for_turn(
        self, session_id: str, message_id: str, tool_names: Iterable[str],
    ) -> list[IntentStateEvent]:
        """生成本轮意图工具完成后应推送的状态事件。"""
        events = []
        for tool_name in tool_names:
            if tool_name not in _EVENT_TOOL_NAMES:
                continue
            state = self.get(session_id).model_dump(mode="json")
            if state.get("intent_status") != "ready_to_confirm":
                events.append(IntentStateEvent(state=state))
                continue
            confirmation = self.get_open_confirmation(session_id)
            if confirmation and confirmation.message_id == message_id:
                state["confirmation_id"] = confirmation.confirmation_id
                state["message_id"] = confirmation.message_id
            events.append(IntentStateEvent(state=state))
        return events
