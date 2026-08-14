"""测试共享工具：临时 Engine 与 sessions 父行种子。

各 repo / service 测试本要重复建临时 Engine 与插会话父行，统一收敛到这里，
配合各测试文件裸跑 main() 的既有风格。
"""
from __future__ import annotations

import tempfile
import types
from pathlib import Path

from sqlalchemy import Engine

from chorus.domain.memory import MemoryRecall
from chorus.domain.session import Session
from chorus.repo.engine import build_engine
from chorus.repo.session import SessionRepository


def fresh_engine(db_name: str = "t.db") -> Engine:
    """返回指向临时目录的 Engine（自动建库与全部表）。"""
    return build_engine(Path(tempfile.mkdtemp()) / db_name)


def seed_session(engine: Engine, sid: str = "s1", title: str = "t") -> Session:
    """插一条父行（tasks / messages 等外键引用 sessions.id）。"""
    session = Session(id=sid, title=title, title_generated=False, created_at=0.0, updated_at=0.0)
    SessionRepository(engine).insert(session)
    return session


def stub_chat_model_provider(client, model_id: str = "fake"):
    """构造注入 ChatModelEntry 的假 ChatModelProvider（不经真实 OpenAI / settings）。"""
    from chorus.agents.chat_model import ChatModelEntry
    entry = ChatModelEntry(client=client, model_id=model_id)

    class _Stub:
        def get_entry(self):
            return entry

        def bypass_entry(self):
            return entry

    return _Stub()


def stub_memory_service():
    """记忆服务空 stub：所有方法恒返空/空操作，供不关心记忆的测试注入。"""
    return types.SimpleNamespace(
        recall_for=lambda agent_type, task_hint: MemoryRecall(),
        extract=lambda session_id: None,
        consolidate=lambda: None,
        record_selection=lambda task_id, agent_type: None,
        record_publication=lambda task_id, agent_type: None,
        record_correction=lambda task_id, agent_type, feedback: None,
    )
