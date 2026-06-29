# kitty/tests/test_service_session.py
"""SessionService 编排层 smoke test：会话元数据 CRUD + per-session 锁 + 标题归一。

覆盖 ``kitty/services/session.py``：create/exists/get（未知 raise KeyError）/rename
（空/超长拒绝）/touch（刷新 updated_at）/delete（CASCADE 带走 messages）/load（DB 灌缓存）
/list（按 updated_at 倒序）/is_title_set+set_title（已设则 no-op）/get_lock（同会话同锁对象、
跨会话不同、非阻塞 acquire 即 409 busy 语义、未知会话拒绝发锁）。SessionService 此前仅当
fixture，本文件补其并发原语与 CRUD 的直接断言（缓存语义：get/exists/list/get_lock 读内存
缓存，create/load 才填缓存，故未知 id 在未 load 时 exists 返回 False）。

运行：.venv/bin/python -m kitty.tests.test_service_session
"""
from __future__ import annotations

import threading

import pytest

from chorus.domain.session import Session, SessionSummary
from chorus.repositories.message import MessageRepository
from chorus.repositories.session import SessionRepository
from chorus.repositories.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService
from chorus.tests._helpers import fresh_conn


class _Clock:
    """可控行时序：每次调用自增 1.0，便于断言 updated_at 单调递增。"""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _svc():
    return SessionService(SessionRepository(fresh_conn()), clock=_Clock())


def test_create_exists_get():
    svc = _svc()
    s = svc.create("hi")
    assert s.id and s.title == "hi"
    assert s.title_generated is False
    assert svc.exists(s.id) is True
    assert svc.exists("unknown") is False
    assert svc.get(s.id).title == "hi"
    with pytest.raises(KeyError):
        svc.get("unknown")


def test_rename_validates_and_updates():
    svc = _svc()
    s = svc.create("hi")
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


def test_get_lock_per_session_and_busy_semantics():
    svc = _svc()
    s = svc.create("hi")
    s2 = svc.create("two")
    lock_a = svc.get_lock(s.id)
    lock_b = svc.get_lock(s.id)
    assert lock_a is lock_b                            # 同会话同一锁对象
    assert svc.get_lock(s2.id) is not lock_a          # 跨会话不同锁
    assert type(lock_a) is type(threading.Lock())     # 真 threading.Lock
    # 409 busy 语义：非阻塞 acquire，已持有时第二次返回 False
    assert lock_a.acquire(blocking=False) is True
    assert lock_a.acquire(blocking=False) is False
    lock_a.release()
    assert lock_a.acquire(blocking=False) is True     # 释放后可再取
    lock_a.release()
    with pytest.raises(KeyError):                     # 未知会话拒绝发锁
        svc.get_lock("nope")


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
    with pytest.raises(KeyError):                     # 重复删 → KeyError
        svc.delete(s.id)


def test_load_populates_cache_and_list_sorts_by_updated_at():
    conn = fresh_conn()
    repo = SessionRepository(conn)
    repo.insert(Session(id="a", title="A", title_generated=False, created_at=1.0, updated_at=2.0))
    repo.insert(Session(id="b", title="B", title_generated=False, created_at=1.0, updated_at=5.0))
    svc = SessionService(repo)
    assert svc.exists("a") is False                   # load 前缓存空
    svc.load()
    assert svc.exists("a") and svc.exists("b")
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
