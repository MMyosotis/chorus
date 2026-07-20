"""意图状态领域规则断言：IntentState 默认值、IntentStateUpdate 拒绝未知字段、schema 派生。

意图成熟度由 intent_status 表达，next_action 派生已移除，状态翻转交服务层。
"""
from __future__ import annotations

import pytest

from chorus.domain.intent import (
    Intent,
    IntentState,
    IntentStateUpdate,
)


def test_intent_state_defaults():
    state = IntentState(session_id="s1")
    assert state.intent_status == "empty"
    assert state.topic == ""
    assert state.style == ""
    assert state.image_count == 3
    assert state.extra == {}
    assert state.missing_slots == []
    assert state.version == 0


def test_update_rejects_unknown_fields():
    """IntentStateUpdate extra=forbid，传废弃字段应抛错。"""
    with pytest.raises(Exception):
        IntentStateUpdate(
            intent_status="empty", topic="", style="", image_count=3,
            extra={}, missing_slots=[],
            goal="已废弃",  # 已并入 topic
        )


def test_update_requires_intent_status():
    """intent_status 无默认，必填。"""
    with pytest.raises(Exception):
        IntentStateUpdate(topic="x")


def test_tool_schema_properties_derives_clean():
    """从模型字段派生 schema，清 title/default 噪音。"""
    props = Intent.tool_schema_properties("topic", "image_count")
    assert set(props) == {"topic", "image_count"}
    for field_schema in props.values():
        assert "title" not in field_schema
        assert "default" not in field_schema
    assert props["image_count"]["type"] == "integer"
    assert "description" in props["topic"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
