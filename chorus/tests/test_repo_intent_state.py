"""IntentStateRepository 新契约与旧 missing_slots 表迁移。"""

from __future__ import annotations

from chorus.domain.intent import IntentState
from chorus.repo.intent_state import IntentStateRepository
from chorus.tests._helpers import fresh_conn, seed_session


_LEGACY_DDL = """
CREATE TABLE intent_states (
    session_id TEXT PRIMARY KEY,
    intent_status TEXT NOT NULL,
    topic TEXT NOT NULL,
    platform TEXT NOT NULL,
    format TEXT NOT NULL,
    style TEXT NOT NULL,
    image_count INTEGER NOT NULL,
    extra TEXT NOT NULL,
    missing_slots TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""


def test_legacy_missing_slots_schema_migrates_to_progress_percent():
    conn = fresh_conn()
    seed_session(conn)
    conn.ensure_schema(_LEGACY_DDL)
    conn.get().execute(
        """
        INSERT INTO intent_states(
            session_id, intent_status, topic, platform, format, style,
            image_count, extra, missing_slots, version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "s1", "needs_clarification", "咖啡馆探店", "小红书", "图文",
            "克制", 3, "{}", '["受众"]', 2, 1.0,
        ),
    )

    repo = IntentStateRepository(conn)
    state = repo.get("s1")
    columns = {
        row["name"]
        for row in conn.get().execute("PRAGMA table_info(intent_states)").fetchall()
    }

    assert state is not None
    assert state.progress_percent == 65
    assert "progress_percent" in columns
    assert "missing_slots" not in columns


def test_progress_percent_round_trips():
    conn = fresh_conn()
    seed_session(conn)
    repo = IntentStateRepository(conn)
    repo.upsert(IntentState(
        session_id="s1",
        intent_status="capturing",
        topic="咖啡馆探店",
        image_count=0,
        progress_percent=42,
    ))

    assert repo.get("s1").progress_percent == 42
