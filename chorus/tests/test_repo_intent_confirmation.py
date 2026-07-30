"""IntentConfirmationRepository smoke：插入/查询/作答翻转/round-trip。"""
from __future__ import annotations

from chorus.domain.intent import IntentConfirmation, IntentConfirmationAnswer
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.tests._helpers import fresh_engine, seed_session


def _confirmation(cid="c1", sid="s1", status="open", created_at=1.0):
    return IntentConfirmation(
        confirmation_id=cid,
        session_id=sid,
        message_id="m-intent",
        topic="咖啡探店",
        platform="网页博客",
        format="图文笔记",
        style="轻松",
        image_count=3,
        extra={"受众": "都市白领"},
        intent_status="ready_to_confirm",
        progress_percent=80,
        status=status,
        created_at=created_at,
    )


def test_insert_and_find_round_trip():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = IntentConfirmationRepository(engine)
    repo.insert(_confirmation())
    got = repo.find_by_session("s1")[0]
    assert got.confirmation_id == "c1"
    assert got.session_id == "s1"
    assert got.message_id == "m-intent"
    assert got.topic == "咖啡探店"
    assert got.intent_status == "ready_to_confirm"
    assert got.image_count == 3
    assert got.extra == {"受众": "都市白领"}
    assert got.status == "open"


def test_find_open_by_session_returns_latest():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = IntentConfirmationRepository(engine)
    repo.insert(_confirmation(cid="c1", status="answered", created_at=1.0))
    repo.insert(_confirmation(cid="c2", status="open", created_at=2.0))
    got = repo.find_open_by_session("s1")
    assert got is not None
    assert got.confirmation_id == "c2"


def test_find_open_returns_none_when_all_answered():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = IntentConfirmationRepository(engine)
    repo.insert(_confirmation(cid="c1", status="answered"))
    assert repo.find_open_by_session("s1") is None


def test_update_answered_flips_status_and_retains_answer():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = IntentConfirmationRepository(engine)
    repo.insert(_confirmation(cid="c1", status="open"))
    repo.update_answered("s1", IntentConfirmationAnswer(signal="confirm", label="确认并开始创作"))
    got = repo.find_by_session("s1")[0]
    assert got.status == "answered"
    assert got.answer.label == "确认并开始创作"
    assert repo.find_open_by_session("s1") is None


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
