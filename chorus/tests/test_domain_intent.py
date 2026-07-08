"""意图状态领域规则断言：derive_next_action 派生 + IntentState.public_dict 含派生字段。

next_action 不再由模型填写，由 intent_status 单向派生，集中在此锚定映射。
"""

from __future__ import annotations

from chorus.domain.intent import (
    IntentState,
    IntentStatePatch,
    derive_next_action,
    empty_intent_state,
)


def test_derive_next_action_maps_each_status():
    cases = {
        "empty": "reply_only",
        "capturing": "ask_user",
        "needs_clarification": "ask_user",
        "ready_to_confirm": "wait_user_confirm",
        "confirmed": "create_plan_after_confirm",
        "dispatched": "dispatching",
    }
    for status, expected in cases.items():
        assert derive_next_action(status) == expected, f"{status} -> {expected}"


def test_derive_next_action_unknown_status_falls_back_to_reply_only():
    assert derive_next_action("nonsense") == "reply_only"


def test_public_dict_includes_derived_next_action():
    state = IntentState(session_id="s1", intent_status="ready_to_confirm", goal="写博文")
    data = state.public_dict()
    assert data["next_action"] == "wait_user_confirm"


def test_public_dict_drops_removed_fields():
    state = IntentState(session_id="s1", intent_status="capturing", goal="写博文")
    data = state.public_dict()
    # 砍掉的 4 字段不应对外暴露
    for removed in ("interaction_intent", "open_questions", "confidence"):
        assert removed not in data
    # next_action 是派生字段，存在但不持久化
    assert "next_action" in data


def test_patch_rejects_removed_fields():
    """IntentStatePatch extra=forbid，传砍掉的字段应抛错。"""
    import pytest
    with pytest.raises(Exception):
        IntentStatePatch(
            intent_status="empty", goal="", known_slots={},
            missing_slots=[], confirmation_summary=None,
            interaction_intent="smalltalk",  # 已砍
        )


def test_empty_intent_state_defaults():
    state = empty_intent_state("s1")
    assert state.intent_status == "empty"
    assert state.goal == ""
    assert state.known_slots == {}
    assert state.confirmation_summary is None
    assert derive_next_action(state.intent_status) == "reply_only"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
