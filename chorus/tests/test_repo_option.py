"""OptionPromptRepository smoke：建表/插入/查询/作答翻转/round-trip。"""
from __future__ import annotations

from chorus.domain.option import OptionItem, OptionPrompt
from chorus.repo.option import OptionPromptRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _prompt(pid="p1", sid="s1", question="选哪个", status="open", created_at=1.0):
    return OptionPrompt(
        prompt_id=pid,
        session_id=sid,
        question=question,
        options=[
            OptionItem(signal="0", label="A", description="甲"),
            OptionItem(signal="1", label="B", description="乙"),
        ],
        allow_custom=True,
        created_at=created_at,
        status=status,
    )


def test_insert_and_get_round_trip():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = OptionPromptRepository(conn)
    repo.insert(_prompt())
    got = repo.get("p1")
    assert got is not None
    assert got.prompt_id == "p1"
    assert got.session_id == "s1"
    assert got.question == "选哪个"
    assert got.status == "open"
    assert [o.label for o in got.options] == ["A", "B"]
    assert got.options[0].signal == "0"
    assert got.allow_custom is True


def test_find_open_by_session_returns_latest():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = OptionPromptRepository(conn)
    repo.insert(_prompt(pid="p1", question="旧", status="answered", created_at=1.0))
    repo.insert(_prompt(pid="p2", question="新", status="open", created_at=2.0))
    got = repo.find_open_by_session("s1")
    assert got is not None
    assert got.prompt_id == "p2"


def test_find_open_returns_none_when_all_answered():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = OptionPromptRepository(conn)
    repo.insert(_prompt(pid="p1", status="answered"))
    assert repo.find_open_by_session("s1") is None


def test_update_answered_flips_status():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = OptionPromptRepository(conn)
    repo.insert(_prompt(pid="p1", status="open"))
    repo.update_answered("p1")
    assert repo.get("p1").status == "answered"
    assert repo.find_open_by_session("s1") is None


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
