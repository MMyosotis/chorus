"""IntentStateRepository 契约：进度百分比读写与版本快照。"""
from __future__ import annotations

from chorus.domain.intent import IntentState
from chorus.repo.intent_state import IntentStateRepository
from chorus.tests._helpers import fresh_engine, seed_session


def test_progress_percent_round_trips():
    engine = fresh_engine()
    seed_session(engine)
    repo = IntentStateRepository(engine)
    repo.upsert(IntentState(
        session_id="s1",
        intent_status="capturing",
        topic="咖啡馆探店",
        image_count=0,
        progress_percent=42,
    ))

    assert repo.get("s1").progress_percent == 42


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
