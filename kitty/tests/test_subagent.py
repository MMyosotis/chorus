#!/usr/bin/env python3
"""SubAgentService.run 的 smoke test：ReAct + 产物解析 + CAS awaiting_confirm/finished。

运行：.venv/bin/python -m kitty.tests.test_subagent
"""
from __future__ import annotations

import json
import tempfile
import types
from pathlib import Path

from kitty.agents.subagent import SubAgentService
from kitty.domain.session import Session
from kitty.domain.task import Task, TaskStatus
from kitty.hooks import HookRegistry, TraceEmitter
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.task import TaskRepository
from kitty.repositories.task_artifacts import TaskArtifactsRepository
from kitty.repositories.task_steps import TaskStepsRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.message import MessageService
from kitty.tools import Tool, ToolContext, ToolRegistry


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [
            types.SimpleNamespace(choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)])
            for d, fr in deltas
        ]

    def __iter__(self):
        return iter(self._chunks)


class FakeClient:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._scripts.pop(0)


class FakeTool(Tool):
    name = "baidu_search"
    description = "x"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        return "search-result"


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    steps_repo = TaskStepsRepository(conn)
    msg_svc = MessageService(msg_repo, trace_repo)
    return conn, msg_svc, task_repo, art_repo, steps_repo


def _mk_task(task_repo, agent_type="idea", status="running", deps=None):
    t = Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type=agent_type, seq=1,
        status=status, invoke_message="骨架：主题=测试", dependencies=deps or [],
        created_at=0.0, updated_at=0.0,
    )
    task_repo.insert(t)
    return t


def _build_subagent(conn, msg_svc, task_repo, art_repo, steps_repo, fake_client):
    hooks = HookRegistry()
    trace = TraceEmitter(msg_svc, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    tool_registry = ToolRegistry([FakeTool()])

    def tool_ctx_factory(session_id, image_model=None):
        return ToolContext(skill_loader=None, session_id=session_id, image_model=image_model)

    _entry = types.SimpleNamespace(client=fake_client, model_id="fake")
    return SubAgentService(
        conn, msg_svc, task_repo, art_repo, steps_repo,
        tool_registry, tool_ctx_factory, hooks,
        {"fake": _entry}, {"idea": "fake", "finalize": "fake"},
        1024, tool_registry.schemas_openai(),
    )


def test_subagent_idea_awaiting_confirm():
    """idea 子 Agent：无工具轮直接产出 → CAS running→awaiting_confirm + 写 artifacts/steps。"""
    conn, msg_svc, task_repo, art_repo, steps_repo = _setup()
    _mk_task(task_repo, "idea", "running")
    # 一轮文本回复（产出协议）
    artifacts = {"candidates": [{"index": 0, "title": "t", "angle": "a", "reason": "r"}], "selected": None}
    narrative = {"busy_lines": ["x"], "awaiting_line": "y", "done_line": "定了"}
    content = (
        f"<<<ARTIFACTS:json>>>\n{json.dumps(artifacts)}\n<<<ARTIFACTS_END>>>\n"
        f"<<<NARRATIVE:json>>>\n{json.dumps(narrative)}\n<<<NARRATIVE_END>>>"
    )
    client = FakeClient([FakeStream([({"content": content}, "stop")])])
    sub = _build_subagent(conn, msg_svc, task_repo, art_repo, steps_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM.value
    art = art_repo.load("t1")
    assert art.artifacts["candidates"][0]["title"] == "t"
    assert art.narrative["done_line"] == "定了"
    steps = steps_repo.list_by_task("t1")
    assert len(steps) == 1 and steps[0].finish_reason == "stop"


def test_subagent_finalize_finished():
    """finalize 子 Agent：产出 PostCard → CAS running→finished（不走 awaiting_confirm）。"""
    conn, msg_svc, task_repo, art_repo, steps_repo = _setup()
    _mk_task(task_repo, "finalize", "running")
    card = {"title": "夏日晚风", "cover": {"url": "http://x/a.jpg"},
            "sections": [{"kind": "paragraph", "text": "一段"}],
            "tags": ["#夏天"], "summary": "摘要"}
    narrative = {"busy_lines": [], "awaiting_line": "", "done_line": "汇总完成"}
    content = (
        f"<<<ARTIFACTS:json>>>\n{json.dumps(card)}\n<<<ARTIFACTS_END>>>\n"
        f"<<<NARRATIVE:json>>>\n{json.dumps(narrative)}\n<<<NARRATIVE_END>>>"
    )
    client = FakeClient([FakeStream([({"content": content}, "stop")])])
    sub = _build_subagent(conn, msg_svc, task_repo, art_repo, steps_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FINISHED.value
    assert art_repo.load("t1").artifacts["title"] == "夏日晚风"


def test_subagent_react_with_tool():
    """子 Agent 先调工具再产出：两轮 ReAct，task_steps 两行。"""
    conn, msg_svc, task_repo, art_repo, steps_repo = _setup()
    _mk_task(task_repo, "idea", "running")
    artifacts = {"candidates": [{"index": 0, "title": "t", "angle": "a", "reason": "r"}], "selected": None}
    narrative = {"busy_lines": ["x"], "awaiting_line": "y", "done_line": "z"}
    content = (
        f"<<<ARTIFACTS:json>>>\n{json.dumps(artifacts)}\n<<<ARTIFACTS_END>>>\n"
        f"<<<NARRATIVE:json>>>\n{json.dumps(narrative)}\n<<<NARRATIVE_END>>>"
    )
    # 第 1 轮工具调用，第 2 轮产出
    client = FakeClient([
        FakeStream([({"tool_calls": [types.SimpleNamespace(
            index=0, id="c1", function=types.SimpleNamespace(name="baidu_search", arguments="{}"))]}, "tool_calls")]),
        FakeStream([({"content": content}, "stop")]),
    ])
    sub = _build_subagent(conn, msg_svc, task_repo, art_repo, steps_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM.value
    steps = steps_repo.list_by_task("t1")
    assert len(steps) == 2
    assert steps[0].tool_calls[0]["name"] == "baidu_search"
    assert steps[1].finish_reason == "stop"


def test_subagent_failed_on_bad_output():
    """产物解析失败（缺段）→ CAS running→failed。"""
    conn, msg_svc, task_repo, art_repo, steps_repo = _setup()
    _mk_task(task_repo, "idea", "running")
    client = FakeClient([FakeStream([({"content": "乱七八糟没有段"}, "stop")])])
    sub = _build_subagent(conn, msg_svc, task_repo, art_repo, steps_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED.value
    assert task_repo.get("t1").error  # 有错误信息


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
