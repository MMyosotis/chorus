#!/usr/bin/env python3
"""SupervisorService 顺序契约：only_reply / new_plan / 校验失败降级。

运行：.venv/bin/python -m kitty.tests.test_supervisor
"""
from __future__ import annotations

import json
import tempfile
import types
from pathlib import Path

from kitty.agents.supervisor import ChatModelEntry, SupervisorService
from kitty.domain.skill import SkillLoader
from kitty.domain.task import ACTIVE_STATUSES, Task
from kitty.hooks import HookRegistry, RollbackHandler, TraceEmitter
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.task import TaskRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.message import MessageService
from kitty.services.session import SessionService


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [types.SimpleNamespace(
            choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)]
        ) for d, fr in deltas]

    def __iter__(self):
        return iter(self._chunks)


class FakeClient:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._scripts.pop(0)


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn)  # 建表
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    session_svc = SessionService(SessionRepository(conn))
    msg_svc = MessageService(msg_repo, trace_repo)
    return conn, session_svc, msg_svc, task_repo


def _build_supervisor(conn, session_svc, msg_svc, task_repo, fake_client):
    skill_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
    skill_loader.load()
    hooks = HookRegistry()
    trace = TraceEmitter(msg_svc, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Error", RollbackHandler(msg_svc).on_error)
    entry = ChatModelEntry(client=fake_client, model_id="fake")
    return SupervisorService(
        session_svc, msg_svc, skill_loader, hooks, {"fake": entry},
        "fake", 1024, task_repo, conn,
    )


def _plan_args(topic="夏日晚风", steps=None):
    if steps is None:
        steps = [
            {"agent_type": "idea", "deps": [], "focus": "选题"},
            {"agent_type": "finalize", "deps": [0], "focus": "汇总"},
        ]
    return {
        "thought": "想了一下",
        "friendly_reply": "好的，我来帮你创作",
        "intent": {"topic": topic, "style": "轻松", "image_count": 2},
        "steps": steps,
    }


def test_only_reply():
    """无 tool_call → only_reply：事件 [message_start, token+, done]，落 user+assistant。"""
    conn, session_svc, msg_svc, task_repo = _setup()
    client = FakeClient([FakeStream([({"content": "你好呀"}, "stop")])])
    sup = _build_supervisor(conn, session_svc, msg_svc, task_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "hi"))
    types_seq = [e.type for e in events]
    assert types_seq[0] == "message_start"
    assert "token" in types_seq
    assert types_seq[-1] == "done"
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant"]


def test_new_plan():
    """create_plan tool_call → 校验通过 → 落库 + TaskPlanCreatedEvent + friendly_reply 气泡。"""
    conn, session_svc, msg_svc, task_repo = _setup()
    args = _plan_args()
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="create_plan", arguments=json.dumps(args)))]}, "tool_calls")])
    client = FakeClient([tool_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, task_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "帮我写一篇夏日博文"))
    types_seq = [e.type for e in events]
    assert "task_plan_created" in types_seq
    assert types_seq[-1] == "done"
    # tasks 落库
    assert task_repo.count_by_session_statuses(s.id, ACTIVE_STATUSES) == 2
    # create_plan tool_call 不落库（只有 user + friendly_reply assistant 气泡）
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "好的，我来帮你创作"


def test_new_plan_blocked_by_active():
    """已有 active task → new_plan 被拒 → 降级 only_reply。"""
    conn, session_svc, msg_svc, task_repo = _setup()
    args = _plan_args()
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="create_plan", arguments=json.dumps(args)))]}, "tool_calls")])
    text_stream = FakeStream([({"content": "你已有进行中的任务"}, "stop")])
    client = FakeClient([tool_stream, text_stream])  # 先 tool_call(被拒) 再降级文本
    sup = _build_supervisor(conn, session_svc, msg_svc, task_repo, client)
    s = session_svc.create("test")
    task_repo.insert(Task(id="active1", session_id=s.id, pipeline_id="p1", agent_type="idea",
                          seq=1, status="running", invoke_message="x", dependencies=[],
                          created_at=0.0, updated_at=0.0))
    events = list(sup.stream(s.id, "再帮我写一篇"))
    types_seq = [e.type for e in events]
    assert "task_plan_created" not in types_seq  # 被拒
    assert types_seq[-1] == "done"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
