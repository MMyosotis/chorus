"""把确认和选项留档折叠回对应助手气泡。"""

from __future__ import annotations

from chorus.domain.intent import IntentConfirmation, IntentConfirmationView
from chorus.domain.option import OptionPrompt, OptionPromptView
from chorus.domain.session.bubbles import find_bubble
from chorus.domain.session.entries import (
    BubbleEntry,
    IntentRecap,
    OptionRecap,
    Recap,
)


def fold_confirmation_recaps(entries: list[BubbleEntry], confirmations: list[IntentConfirmation]) -> None:
    for confirmation in confirmations:
        if confirmation.status != "answered" or confirmation.message_id is None:
            continue
        append_recap(entries, confirmation.message_id, IntentRecap(
            id=f"intent-confirm:{confirmation.confirmation_id}",
            intent_state=IntentConfirmationView.from_confirmation(confirmation),
        ))


def fold_option_recaps(entries: list[BubbleEntry], prompts: list[OptionPrompt]) -> None:
    for prompt in prompts:
        if prompt.status != "answered" or prompt.message_id is None:
            continue
        append_recap(entries, prompt.message_id, OptionRecap(
            id=f"option:{prompt.prompt_id}",
            option_prompt=OptionPromptView.from_prompt(prompt),
        ))


def append_recap(entries: list[BubbleEntry], anchor: str, recap: Recap) -> None:
    found = find_bubble(entries, anchor)
    if found is None:
        return
    index, bubble = found
    entries[index] = bubble.model_copy(update={"recaps": [*bubble.recaps, recap]})
