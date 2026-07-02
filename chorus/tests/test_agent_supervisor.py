"""SupervisorService 顺序契约：only_reply / new_plan / 校验失败降级。

运行：.venv/bin/python -m kitty.tests.test_agent_supervisor
"""
from __future__ import annotations

import json
import tempfile
import types
from pathlib import Path

from chorus.agents.supervisor import SupervisorService
from chorus.domain.skill import SkillLoader
from chorus.domain.task import ACTIVE_STATUSES, Task
from chorus.hooks import ErrorFinalizer, HookRegistry, TraceEmitter
from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService
from chorus.tests._helpers import stub_chat_model_provider
from chorus.tools import ToolDispatch
from chorus.tools.builtin import CreatePlanTool, LoadSkillTool


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


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn)  # 建表
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    content_repo = TaskContentRepository(conn)
    session_svc = SessionService(SessionRepository(conn))
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, trace_svc)
    return conn, session_svc, msg_svc, trace_svc, task_repo, content_repo


def _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, fake_client):
    skill_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
    hooks = HookRegistry()
    trace = TraceEmitter(trace_svc, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Error", ErrorFinalizer(msg_svc).on_error)
    tool_dispatcher = ToolDispatch([CreatePlanTool(task_repo, content_repo, conn), LoadSkillTool(skill_loader)], _stub_settings())

    entry = stub_chat_model_provider(fake_client)
    return SupervisorService(
        session_svc, msg_svc, skill_loader, hooks, entry,
        1024, task_repo, tool_dispatcher,
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
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    client = FakeClient([FakeStream([({"content": "你好呀"}, "stop")])])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "hi"))
    types_seq = [e.type for e in events]
    assert types_seq[0] == "message_start"
    assert "token" in types_seq
    assert types_seq[-1] == "done"
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant"]


def test_new_plan():
    """create_plan tool_call → dispatch Terminal → 建图落库 + done；assistant(tool_calls)+tool 成对落库。"""
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    args = _plan_args()
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="create_plan", arguments=json.dumps(args)))]}, "tool_calls")])
    client = FakeClient([tool_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "帮我写一篇夏日博文"))
    types_seq = [e.type for e in events]
    assert "task_plan_created" not in types_seq   # 已删
    assert types_seq[-1] == "done"
    # tasks 落库
    assert task_repo.count_by_session_statuses(s.id, ACTIVE_STATUSES) == 2
    # 历史如实：user + assistant(friendly_reply, tool_calls=[create_plan]) + tool(result)
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool"]
    assert msgs[1].content == "好的，我来帮你创作"
    assert len(msgs[1].tool_calls) == 1
    assert msgs[1].tool_calls[0].name == "create_plan"
    assert msgs[2].tool_call_id == "c1"
    assert msgs[2].name == "create_plan"


def test_reply_outcome_pairs_and_continues():
    """Reply 型 tool_call 成对落库 + loop 继续到第二轮文本回复 + done。

    锚定 OpenAI tool_calls/tool 配对约束：Reply 分支须先 append assistant(tool_calls=[call])
    再 append tool(result)，否则下一轮 build_provider_messages 回放孤儿 tool 消息。
    用真实 LoadSkillTool 加载不存在的技能名 → Reply("Error: skill '...' not found...")，
    下一轮模型回文本。终态历史须为 [user, assistant(tool_calls), tool, assistant(文本)]。
    """
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    # 第一轮：load_skill("ghost") → Reply(未命中技能错误串)
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="load_skill", arguments=json.dumps({"name": "ghost"})))]}, "tool_calls")])
    # 第二轮：纯文本回复（loop 继续）
    text_stream = FakeStream([({"content": "已为你查到"}, "stop")])
    client = FakeClient([tool_stream, text_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "帮我加载 ghost 技能"))
    types_seq = [e.type for e in events]
    assert types_seq[-1] == "done"
    # 历史如实：user + assistant(tool_calls=[load_skill]) + tool(result) + assistant(文本)
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool", "assistant"]
    assert len(msgs[1].tool_calls) == 1
    assert msgs[1].tool_calls[0].name == "load_skill"
    assert msgs[2].role == "tool"
    assert msgs[2].tool_call_id == "c1"
    assert msgs[2].name == "load_skill"
    assert msgs[3].role == "assistant"
    assert (msgs[3].tool_calls or []) == []
    assert msgs[3].content == "已为你查到"


def test_multi_reply_tool_calls_in_one_turn_persists_one_assistant():
    """一轮内 ≥2 个 Reply tool_call → 收集后落一条 assistant(tool_calls=[全部])+N tool，
    消除多 Reply 复用 message_id 撞 messages PK 的回归（并行 baidu_search 等场景）。

    锚定 OpenAI 多 tool_call 配对结构：一条 assistant 携带全部 tool_calls → N 条 tool
    结果。2× load_skill(不存在技能名) 均 Reply，下一轮模型回文本。终态历史须为
    [user, assistant(2 tool_calls), tool, tool, assistant(文本)]。
    """
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    # 第一轮：2 个 load_skill tool_call（index 0/1），均 Reply(未命中技能错误串)
    tool_stream = FakeStream([({
        "tool_calls": [
            types.SimpleNamespace(
                index=0, id="c1",
                function=types.SimpleNamespace(
                    name="load_skill", arguments=json.dumps({"name": "ghost"})),
            ),
            types.SimpleNamespace(
                index=1, id="c2",
                function=types.SimpleNamespace(
                    name="load_skill", arguments=json.dumps({"name": "phantom"})),
            ),
        ],
    }, "tool_calls")])
    # 第二轮：纯文本回复（loop 继续）
    text_stream = FakeStream([({"content": "两个技能都没找到"}, "stop")])
    client = FakeClient([tool_stream, text_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "帮我加载 ghost 和 phantom 技能"))
    types_seq = [e.type for e in events]
    # 无 PK 冲突 → 无 error；正常结束 done
    assert "error" not in types_seq
    assert types_seq[-1] == "done"
    # 历史如实：user + assistant(2 tool_calls) + tool + tool + assistant(文本)
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool", "tool", "assistant"]
    assert len(msgs[1].tool_calls) == 2          # 一条 assistant 携带两个 tool_call
    assert msgs[2].tool_call_id == "c1"          # 顺序保留
    assert msgs[3].tool_call_id == "c2"


def test_new_plan_blocked_by_active_task():
    """会话有 active task → stream 入口 yield BusyEvent，user 消息不入库。"""
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    args = _plan_args()
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="create_plan", arguments=json.dumps(args)))]}, "tool_calls")])
    client = FakeClient([tool_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    task_repo.insert(Task(id="active1", session_id=s.id, pipeline_id="p1", agent_type="idea",
                          status="running", dependencies=[],
                          created_at=0.0, updated_at=0.0))
    events = list(sup.stream(s.id, "再帮我写一篇"))
    types_seq = [e.type for e in events]
    assert types_seq == ["busy"]              # 只 yield BusyEvent
    assert task_repo.count_by_session_statuses(s.id, ACTIVE_STATUSES) == 1  # 未新增
    # user 消息不入库
    msgs = msg_svc.list_messages(s.id)
    assert msgs == []


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
