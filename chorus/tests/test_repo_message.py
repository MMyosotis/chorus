"""MessageRepository + MessageService smoke test：三角色回环。

运行：``.venv/bin/python -m chorus.tests.test_repo_message``
"""
from __future__ import annotations

from chorus.repositories.message import MessageRepository
from chorus.repositories.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)
    return MessageService(MessageRepository(conn), TraceRepository(conn))


def test_three_role_roundtrip():
    svc = _setup()
    svc.append_user_message("s1", "hi")
    svc.append_assistant_message("s1", message_id="m1", content="yo", tool_calls=[])
    svc.append_tool_message("s1", tool_call_id="c1", name="search", content="r")
    msgs = svc.list_messages("s1")
    assert [m.role for m in msgs] == ["user", "assistant", "tool"]
    assert msgs[1].content == "yo"
    assert msgs[2].tool_call_id == "c1"


def main():
    test_three_role_roundtrip()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
