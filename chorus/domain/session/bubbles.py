"""把原始消息合并成前端对话气泡。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Union

from chorus.domain.intent import IntentConfirmation
from chorus.domain.message import MessageView
from chorus.domain.option import OptionPrompt
from chorus.domain.session.entries import AssistantBubble, BubbleEntry, UserEntry


@dataclass(frozen=True)
class _AssistantTurn:
    message: MessageView
    has_content: bool
    suspended: bool
    plan_created: bool


@dataclass(frozen=True)
class _BubbleState:
    bubble: AssistantBubble
    plan_created: bool
    entry_index: int


class _BubbleAccumulator:
    """维护会话气泡装配过程的临时状态。"""

    def __init__(self, suspended_anchors: set[str], plan_anchors: set[str]):
        self._suspended_anchors = suspended_anchors
        self._plan_anchors = plan_anchors
        self._entries: list[BubbleEntry] = []
        self._current: Optional[_BubbleState] = None

    @property
    def entries(self) -> list[BubbleEntry]:
        return self._entries

    def consume(self, message: MessageView) -> None:
        if message.role == "assistant":
            self._consume_assistant(message)
            return
        self._consume_user(message)

    def _consume_user(self, message: MessageView) -> None:
        self._entries.append(UserEntry(id=message.id, content=message.content))
        self._current = None

    def _consume_assistant(self, message: MessageView) -> None:
        if _is_plan_boundary(self._current):
            self._current = None
        turn = _classify_assistant_turn(message, self._suspended_anchors, self._plan_anchors)
        if turn is not None:
            self._accept_turn(turn)

    def _accept_turn(self, turn: _AssistantTurn) -> None:
        current = self._current
        if current is None:
            self._start_new_bubble(turn)
            return
        self._merge_current_bubble(current, turn)

    def _start_new_bubble(self, turn: _AssistantTurn) -> None:
        current = _start_bubble(turn, len(self._entries))
        self._entries.append(current.bubble)
        self._current = current

    def _merge_current_bubble(self, current: _BubbleState, turn: _AssistantTurn) -> None:
        merged = _merge_bubble(current, turn)
        self._entries[merged.entry_index] = merged.bubble
        self._current = merged


def build_bubbles(
    messages: list[MessageView],
    suspended_anchors: set[str],
    plan_anchors: set[str],
) -> list[BubbleEntry]:
    """按对话顺序产出渲染条目：一次交互链路的助手轮次合并成单气泡。"""
    accumulator = _BubbleAccumulator(suspended_anchors, plan_anchors)
    for message in messages:
        accumulator.consume(message)
    return accumulator.entries


def _classify_assistant_turn(
    message: MessageView,
    suspended_anchors: set[str],
    plan_anchors: set[str],
) -> Optional[_AssistantTurn]:
    """把有效助手消息转换为合并阶段需要的状态。"""
    has_content = bool(message.content and message.content.strip())
    has_tools = bool(message.tools)
    if not has_content and not has_tools:
        return None
    return _AssistantTurn(
        message=message,
        has_content=has_content,
        suspended=(message.id in suspended_anchors or (not has_content and has_tools)),
        plan_created=message.id in plan_anchors,
    )


def _start_bubble(turn: _AssistantTurn, entry_index: int) -> _BubbleState:
    """从首条有效助手消息创建气泡状态。"""
    message = turn.message
    bubble = AssistantBubble(
        id=message.id,
        content=message.content or "",
        tools=list(message.tools),
        message_ids=[message.id] if message.id else [],
        recaps=[],
        suspended=turn.suspended,
    )
    return _BubbleState(
        bubble=bubble,
        plan_created=turn.plan_created,
        entry_index=entry_index,
    )


def _merge_bubble(current: _BubbleState, turn: _AssistantTurn) -> _BubbleState:
    """把后续助手消息合并到当前气泡状态。"""
    message = turn.message
    separator = "\n\n" if current.bubble.content and turn.has_content else ""
    content = current.bubble.content + separator + (message.content if turn.has_content else "")
    message_ids = current.bubble.message_ids
    if message.id and message.id not in message_ids:
        message_ids = [*message_ids, message.id]
    return _BubbleState(
        bubble=current.bubble.model_copy(update={
            "content": content,
            "tools": [*current.bubble.tools, *message.tools],
            "message_ids": message_ids,
            "suspended": turn.suspended,
        }),
        plan_created=current.plan_created or turn.plan_created,
        entry_index=current.entry_index,
    )


def _is_plan_boundary(state: Optional[_BubbleState]) -> bool:
    """成功建图的待回执气泡是流水线边界。"""
    return state is not None and state.bubble.suspended and state.plan_created


def anchor_ids(items: Iterable[Union[IntentConfirmation, OptionPrompt]]) -> set[str]:
    """留档记录锚定的助手消息标识集合，缺锚点的忽略。"""
    return {item.message_id for item in items if item.message_id is not None}


def find_bubble(entries: list[BubbleEntry], message_id: str) -> Optional[tuple[int, AssistantBubble]]:
    for index, entry in enumerate(entries):
        if not isinstance(entry, AssistantBubble) or message_id not in entry.message_ids:
            continue
        return index, entry
    return None
