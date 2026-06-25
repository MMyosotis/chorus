"""MessageRepository + MessageService smoke test：subtype 回环 / progress 压缩 / 并发 seq 重试。

运行：``.venv/bin/python -m kitty.tests.test_repo_message``
"""
from __future__ import annotations

import threading

from kitty.repositories.message import MessageRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.message import MessageService
from kitty.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)
    return MessageService(MessageRepository(conn), TraceRepository(conn))


def test_subtype_roundtrip():
    svc = _setup()
    svc.append_user_message("s1", "hi")
    svc.append_progress_message("s1", message_id="m1", content="选题官接单啦\n第二行")
    msgs = svc.list_messages("s1")
    assert msgs[1].subtype == "progress"
    assert msgs[0].subtype is None


def test_progress_provider_dict_compact():
    svc = _setup()
    msg = svc.append_progress_message("s1", message_id="m1", content="文案初稿完成，等你确认\n这是详细话术")
    d = msg.to_provider_dict()
    assert d["content"].startswith("[进度] ")
    assert "详细话术" not in d["content"]  # 被压成单行


def test_concurrent_append_no_seq_collision():
    svc = _setup()
    errors = []

    def worker():
        try:
            for _ in range(5):
                svc.append_user_message("s1", "x")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    # 4 worker * 5 = 20 条 + 0（无 user 前置），全落库无丢失
    assert len(svc.list_messages("s1")) == 20


def main():
    test_subtype_roundtrip()
    test_progress_provider_dict_compact()
    test_concurrent_append_no_seq_collision()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
