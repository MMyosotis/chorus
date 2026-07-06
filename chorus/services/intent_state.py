"""意图状态服务：主 Agent 工作记忆的读写与确认门禁。"""

from __future__ import annotations

import time

from chorus.domain.intent import IntentState, IntentStatePatch, empty_intent_state
from chorus.repo.intent_state import IntentStateRepository
from chorus.services.session import SessionService


class IntentStateService:
    def __init__(self, repo: IntentStateRepository, session_service: SessionService):
        self._repo = repo
        self._session = session_service

    def get(self, session_id: str) -> IntentState:
        state = self._repo.get(session_id)
        return state if state is not None else empty_intent_state(session_id)

    def update_from_tool(self, session_id: str, patch: IntentStatePatch) -> IntentState:
        current = self.get(session_id)
        state = IntentState(
            session_id=session_id,
            interaction_intent=patch.interaction_intent,
            intent_status=patch.intent_status,
            goal=patch.goal,
            known_slots=patch.known_slots,
            missing_slots=patch.missing_slots,
            open_questions=patch.open_questions,
            confirmation_summary=patch.confirmation_summary,
            next_action=patch.next_action,
            confidence=patch.confidence,
            version=current.version + 1,
            updated_at=time.time(),
        )
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def confirm(self, session_id: str) -> IntentState:
        current = self.get(session_id)
        state = current.model_copy(
            update={
                "intent_status": "confirmed",
                "next_action": "create_plan_after_confirm",
                "version": current.version + 1,
                "updated_at": time.time(),
            }
        )
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def reopen(self, session_id: str) -> IntentState:
        current = self.get(session_id)
        state = current.model_copy(
            update={
                "intent_status": "needs_clarification",
                "next_action": "ask_user",
                "version": current.version + 1,
                "updated_at": time.time(),
            }
        )
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def mark_dispatched(self, session_id: str) -> IntentState:
        current = self.get(session_id)
        state = current.model_copy(
            update={
                "intent_status": "dispatched",
                "next_action": "dispatching",
                "version": current.version + 1,
                "updated_at": time.time(),
            }
        )
        self._repo.upsert(state)
        self._session.touch(session_id)
        return state

    def is_confirmed(self, session_id: str) -> bool:
        return self.get(session_id).intent_status == "confirmed"
