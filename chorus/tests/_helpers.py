"""测试共享工具：临时 DB 连接 + sessions 父行种子。

各 repo / service 测试本要重复建临时连接与插会话父行，统一收敛到这里，
配合各测试文件裸跑 main() 的既有风格。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.session import Session
from chorus.repo.connection import ConnectionFactory
from chorus.repo.session import SessionRepository


def fresh_conn(db_name: str = "t.db") -> ConnectionFactory:
    """返回指向临时目录的 ConnectionFactory（自动建库；线程局部连接）。"""
    return ConnectionFactory(Path(tempfile.mkdtemp()) / db_name)


def seed_session(conn: ConnectionFactory, sid: str = "s1", title: str = "t") -> Session:
    """建 sessions 表并插一条父行（tasks / messages 等外键引用 sessions.id）。

    返回插入的 Session，供断言或引用。
    """
    session = Session(id=sid, title=title, title_generated=False, created_at=0.0, updated_at=0.0)
    SessionRepository(conn).insert(session)
    return session


def stub_chat_model_provider(client, model_id: str = "fake"):
    """构造注入 ChatModelEntry 的假 ChatModelProvider（不经真实 OpenAI / settings）。

    supervisor/subagent 测试用：get_entry() 恒返回包好 fake client 的 entry，
    跳过 ChatModelProvider 的 config 解析与 settings 查询。
    """
    from chorus.agents.chat_model import ChatModelEntry
    entry = ChatModelEntry(client=client, model_id=model_id)

    class _Stub:
        def get_entry(self):
            return entry

        def title_entry(self):
            return entry

    return _Stub()

