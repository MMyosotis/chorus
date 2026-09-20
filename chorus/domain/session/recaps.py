"""把确认和选项留档折叠回对应助手气泡。"""

from __future__ import annotations

from chorus.domain.intent import IntentConfirmation
from chorus.domain.option import OptionPrompt
from chorus.domain.session.bubbles import find_bubble
from chorus.domain.session.entries import (
    BubbleEntry,
    IntentRecap,
    OptionRecap,
    Recap,
)


def dump_confirmation(confirmation: IntentConfirmation) -> dict:
    """意图确认留档的传输结构。"""
    return confirmation.model_dump(mode="json", exclude={"session_id"}, exclude_none=True)


def dump_prompt(prompt: OptionPrompt) -> dict:
    """选项征询单的传输结构。"""
    return {
        "prompt_id": prompt.prompt_id,
        "message_id": prompt.message_id,
        "questions": [question.model_dump() for question in prompt.questions],
        "status": prompt.status,
        "answers": [answer.model_dump(exclude_none=True) for answer in prompt.answers],
        "created_at": prompt.created_at,
    }


def fold_confirmation_recaps(entries: list[BubbleEntry], confirmations: list[IntentConfirmation]) -> None:
    for confirmation in confirmations:
        if confirmation.status != "answered" or confirmation.message_id is None:
            continue
        append_recap(entries, confirmation.message_id, IntentRecap(
            id=f"intent-confirm:{confirmation.confirmation_id}",
            intent_state=dump_confirmation(confirmation),
        ))


def fold_option_recaps(entries: list[BubbleEntry], prompts: list[OptionPrompt]) -> None:
    for prompt in prompts:
        if prompt.status != "answered" or prompt.message_id is None:
            continue
        append_recap(entries, prompt.message_id, OptionRecap(
            id=f"option:{prompt.prompt_id}",
            option_prompt=dump_prompt(prompt),
        ))


def append_recap(entries: list[BubbleEntry], anchor: str, recap: Recap) -> None:
    found = find_bubble(entries, anchor)
    if found is None:
        return
    index, bubble = found
    entries[index] = bubble.model_copy(update={"recaps": [*bubble.recaps, recap]})
