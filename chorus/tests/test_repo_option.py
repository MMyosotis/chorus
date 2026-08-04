"""OptionPromptRepository smoke：建表/插入/查询/作答翻转/round-trip。"""
from __future__ import annotations

from chorus.domain.option import OptionAnswer, OptionItem, OptionPrompt, OptionQuestion
from chorus.repo.option import OptionPromptRepository
from chorus.tests._helpers import fresh_engine, seed_session


def _prompt(pid="p1", sid="s1", status="open", created_at=1.0):
    return OptionPrompt(
        prompt_id=pid,
        session_id=sid,
        message_id="m-option",
        questions=[OptionQuestion(
            question="选哪个",
            options=[
                OptionItem(signal="0", label="A", description="甲"),
                OptionItem(signal="1", label="B", description="乙"),
            ],
        )],
        created_at=created_at,
        status=status,
    )


def test_insert_and_get_round_trip():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = OptionPromptRepository(engine)
    repo.insert(_prompt())
    got = repo.get("p1")
    assert got is not None
    assert got.prompt_id == "p1"
    assert got.session_id == "s1"
    assert got.message_id == "m-option"
    assert got.status == "open"
    assert [o.label for o in got.questions[0].options] == ["A", "B"]
    assert got.questions[0].options[0].signal == "0"


def test_find_open_by_session_returns_latest():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = OptionPromptRepository(engine)
    repo.insert(_prompt(pid="p1", status="answered", created_at=1.0))
    repo.insert(_prompt(pid="p2", status="open", created_at=2.0))
    got = repo.find_open_by_session("s1")
    assert got is not None
    assert got.prompt_id == "p2"


def test_find_open_returns_none_when_all_answered():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = OptionPromptRepository(engine)
    repo.insert(_prompt(pid="p1", status="answered"))
    assert repo.find_open_by_session("s1") is None


def test_update_answered_flips_status_and_retains_answer():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = OptionPromptRepository(engine)
    repo.insert(_prompt(pid="p1", status="open"))
    repo.update_answered("s1", [OptionAnswer(signal="1", label="B")])
    got = repo.get("p1")
    assert got.status == "answered"
    assert got.answers[0].label == "B"
    assert repo.find_open_by_session("s1") is None


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
