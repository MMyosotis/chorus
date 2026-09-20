"""会话视图服务：聚合各服务数据喂给领域装配函数，产出前端渲染结构。"""

from __future__ import annotations

from chorus.domain.session_view import build_session_view
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.option import OptionPromptService
from chorus.services.task import TaskService


class SessionViewService:
    def __init__(
        self,
        message: MessageService,
        task: TaskService,
        intent_state: IntentStateService,
        option: OptionPromptService,
    ):
        self._message = message
        self._task = task
        self._intent_state = intent_state
        self._option = option

    def collect(self, session_id: str, *, needs_resume: bool) -> dict:
        """取会话全量视图数据并装配成成品结构，续跑判定由编排方传入。"""
        return build_session_view(
            self._message.history_view(session_id),
            self._task.get_graph(session_id),
            self._task.list_products(session_id),
            self._intent_state.get(session_id),
            self._intent_state.list_confirmations(session_id),
            self._option.list_by_session(session_id),
            needs_resume=needs_resume,
        )
