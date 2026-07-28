"""选项征询服务：提问单的创建、查询与作答翻转。"""

from __future__ import annotations

import time
from typing import Optional

import uuid6

from chorus.domain.option import OptionItem, OptionPrompt
from chorus.repo.option import OptionPromptRepository
from chorus.services.session import SessionService


class OptionPromptService:
    def __init__(self, repo: OptionPromptRepository, session_service: SessionService):
        self._repo = repo
        self._session = session_service

    def create(
        self, session_id: str, question: str,
        options: list[OptionItem], allow_custom: bool,
    ) -> OptionPrompt:
        prompt = OptionPrompt(
            prompt_id=str(uuid6.uuid7()),
            session_id=session_id,
            question=question,
            options=options,
            allow_custom=allow_custom,
            created_at=time.time(),
        )
        self._repo.insert(prompt)
        self._session.touch(session_id)
        return prompt

    def get_open(self, session_id: str) -> Optional[OptionPrompt]:
        return self._repo.find_open_by_session(session_id)

    def mark_answered(self, prompt_id: str) -> None:
        self._repo.update_answered(prompt_id)
