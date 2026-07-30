"""选项征询领域模型：OptionItem/OptionPromptDef/OptionPrompt 构造与字段约束。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from chorus.domain.option import OptionAnswer, OptionItem, OptionPrompt, OptionPromptDef


def test_option_item_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OptionItem(signal="0", label="A", description="d", extra="x")


def test_option_prompt_def_defaults_allow_custom():
    definition = OptionPromptDef(
        question="选哪个",
        options=[OptionItem(signal="0", label="A", description="d")],
    )
    assert definition.allow_custom is True


def test_option_prompt_def_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OptionPromptDef(question="x", options=[], allow_custom=True, bogus=1)


def test_option_prompt_carries_identity_and_status():
    prompt = OptionPrompt(
        prompt_id="p1",
        session_id="s1",
        question="选哪个",
        options=[OptionItem(signal="0", label="A", description="d")],
        allow_custom=False,
    )
    assert prompt.prompt_id == "p1"
    assert prompt.session_id == "s1"
    assert prompt.status == "open"
    assert prompt.created_at > 0
    assert prompt.allow_custom is False


def test_option_prompt_can_retain_answer():
    prompt = OptionPrompt(
        prompt_id="p1",
        session_id="s1",
        question="选哪个",
        options=[OptionItem(signal="0", label="A", description="d")],
        answer=OptionAnswer(signal="0", label="A"),
    )
    assert prompt.answer.label == "A"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
