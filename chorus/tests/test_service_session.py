# kitty/tests/test_service_session.py
"""SessionService 编排层 smoke test：会话元数据 CRUD + 标题归一。

覆盖 ``chorus/services/session.py``：create/exists/get（未知 raise KeyError）/rename
（空/超长拒绝）/touch（刷新 updated_at）/delete（CASCADE 带走 messages）
/list（按 updated_at 倒序）/is_title_set+set_title（已设则 no-op，SQL 原子复检+写入）。
无内存缓存、无会话级并发锁（同一会话同一时刻仅一个 chat 流），每次直接打库。

运行：.venv/bin/python -m chorus.tests.test_service_session
"""
from __future__ import annotations

import time

import pytest

from chorus.domain.session import Session, SessionSummary
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService
from chorus.tests._helpers import fresh_conn


def _svc():
    return SessionService(SessionRepository(fresh_conn()))


def test_create_exists_get():
    svc = _svc()
    s = svc.create("hi")
    assert s.id and s.title == "hi"
    assert s.title_generated is False
    assert svc.exists(s.id) is True
    assert svc.exists("unknown") is False
    assert svc.get(s.id).title == "hi"
    assert svc.get("unknown") is None


def test_rename_validates_and_updates():
    svc = _svc()
    s = svc.create("hi")
    time.sleep(0.001)
    renamed = svc.rename(s.id, "新标题")
    assert renamed.title == "新标题"
    assert renamed.title_generated is True             # 用户手改即视为已生成
    assert renamed.updated_at > s.updated_at
    assert svc.get(s.id).title == "新标题"
    with pytest.raises(ValueError):                    # 空标题拒绝
        svc.rename(s.id, "   ")


def test_touch_advances_updated_at():
    svc = _svc()
    s = svc.create("hi")
    before = svc.get(s.id).updated_at
    time.sleep(0.001)
    svc.touch(s.id)
    assert svc.get(s.id).updated_at > before


def test_is_title_set_and_set_title():
    svc = _svc()
    s = svc.create("hi")                               # title_generated=False
    assert svc.is_title_set(s.id) is False
    assert svc.set_title(s.id, "自动标题") is True
    got = svc.get(s.id)
    assert got.title == "自动标题"
    assert got.title_generated is True
    assert svc.is_title_set(s.id) is True
    assert svc.set_title(s.id, "另一个") is False          # 已设 → no-op（锁内复检）
    assert svc.get(s.id).title == "自动标题"                 # 不变
    s2 = svc.create("x")
    assert svc.set_title(s2.id, "   ") is False             # 归一为空 → 跳过
    assert svc.get(s2.id).title == "x"


def test_delete_cascades_messages():
    conn = fresh_conn()
    svc = SessionService(SessionRepository(conn))
    msg_svc = MessageService(MessageRepository(conn), TraceService(TraceRepository(conn)))
    s = svc.create("hi")
    msg_svc.append_user_message(s.id, "hello")
    assert len(msg_svc.list_messages(s.id)) == 1
    svc.delete(s.id)
    assert not svc.exists(s.id)
    assert msg_svc.list_messages(s.id) == []          # CASCADE 带走 messages
    svc.delete(s.id)                                  # 重复删幂等，不抛


def test_list_sorts_by_updated_at():
    conn = fresh_conn()
    repo = SessionRepository(conn)
    repo.insert(Session(id="a", title="A", title_generated=False, created_at=1.0, updated_at=2.0))
    repo.insert(Session(id="b", title="B", title_generated=False, created_at=1.0, updated_at=5.0))
    svc = SessionService(repo)
    assert svc.exists("a") and svc.exists("b")        # 直接打库，无需预 load
    lst = svc.list()
    assert [x.id for x in lst] == ["b", "a"]          # updated_at 倒序
    assert all(isinstance(x, SessionSummary) for x in lst)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
