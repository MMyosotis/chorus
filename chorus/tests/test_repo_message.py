"""MessageRepository + MessageService smoke test：三角色回环。

运行：``.venv/bin/python -m chorus.tests.test_repo_message``
"""
from __future__ import annotations

import uuid6

from chorus.repo.message import MessageRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.trace import TraceService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)
    return MessageService(MessageRepository(conn), TraceService(TraceRepository(conn)))


def test_three_role_roundtrip():
    svc = _setup()
    svc.append_user_message("s1", "hi")
    # assistant 的 message_id 由调用方预生成（生产由 supervisor 调 uuid6.uuid7()），
    # 须用 uuid7 才能与 user/tool 的 id 同处趋势递增序，ORDER BY id 才正确
    svc.append_assistant_message("s1", message_id=str(uuid6.uuid7()), content="yo", tool_calls=[])
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
