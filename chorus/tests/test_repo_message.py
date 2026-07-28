"""MessageRepository + MessageService smoke test：三角色回环。"""
from __future__ import annotations

import uuid6

from chorus.repo.message import MessageRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.trace import TraceService
from chorus.tests._helpers import fresh_engine, seed_session


def _setup():
    engine = fresh_engine()
    seed_session(engine)
    return MessageService(MessageRepository(engine), TraceService(TraceRepository(engine)))


def test_three_role_roundtrip():
    svc = _setup()
    svc.append_user_message("s1", "hi")
    # 用 uuid7 让 id 趋势递增，排序才正确
    svc.append_assistant_message("s1", message_id=str(uuid6.uuid7()), content="yo", tool_calls=[])
    svc.append_tool_message("s1", tool_call_id="c1", name="search", content="r")
    msgs = svc.list_messages("s1")
    assert [m.role for m in msgs] == ["user", "assistant", "tool"]
    assert msgs[1].content == "yo"
    assert msgs[2].tool_call_id == "c1"


def test_rewrite_last_tool_result():
    """按名取最后一条工具结果并改写内容，供用户拍板后补全真实结局。"""
    svc = _setup()
    svc.append_tool_message("s1", tool_call_id="c1", name="update_intent_state", content="等待用户拍板")
    svc.append_tool_message("s1", tool_call_id="c2", name="search", content="其它工具结果")
    # 改写只命中 update_intent_state 那条，不动 search
    svc.rewrite_last_tool_result("s1", "update_intent_state", "用户已同意，意图进入 confirmed")
    msgs = svc.list_messages("s1")
    assert msgs[0].content == "用户已同意，意图进入 confirmed"
    assert msgs[1].content == "其它工具结果"


def main():
    test_three_role_roundtrip()
    test_rewrite_last_tool_result()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
