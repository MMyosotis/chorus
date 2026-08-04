"""选项征询领域模型：OptionItem/OptionPromptDef/OptionPrompt 构造与字段约束。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from chorus.domain.option import OptionAnswer, OptionItem, OptionPrompt, OptionPromptDef, OptionQuestion


def test_option_item_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OptionItem(signal="0", label="A", description="d", extra="x")


def _question(question="选哪个"):
    return OptionQuestion(
        question=question,
        options=[OptionItem(signal="0", label="A", description="d")],
    )


def test_option_prompt_def_accepts_question_group():
    definition = OptionPromptDef(
        questions=[_question()],
    )
    assert definition.questions[0].allow_custom is True


def test_option_prompt_def_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OptionPromptDef(questions=[_question()], bogus=1)


def test_option_prompt_carries_identity_and_status():
    prompt = OptionPrompt(
        prompt_id="p1",
        session_id="s1",
        questions=[_question()],
    )
    assert prompt.prompt_id == "p1"
    assert prompt.session_id == "s1"
    assert prompt.status == "open"
    assert prompt.created_at > 0
    assert prompt.questions[0].question == "选哪个"


def test_option_prompt_can_retain_answer():
    prompt = OptionPrompt(
        prompt_id="p1",
        session_id="s1",
        questions=[_question()],
        answers=[OptionAnswer(signal="0", label="A")],
    )
    assert prompt.answers[0].label == "A"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
