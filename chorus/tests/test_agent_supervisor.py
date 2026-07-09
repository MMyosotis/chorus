"""SupervisorService 顺序契约：普通回复 / 建图 / 校验失败降级。"""
from __future__ import annotations

import json
import tempfile
import types
from pathlib import Path

from chorus.agents.loop import AgentLoop
from chorus.agents.supervisor import SupervisorService
from chorus.domain.skill import SkillLoader
from chorus.domain.task import ACTIVE_STATUSES, Task
from chorus.hooks import ErrorFinalizer, HookRegistry, TraceEmitter, emit_message_start
from chorus.repo.connection import ConnectionFactory
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService
from chorus.tests._helpers import stub_chat_model_provider
from chorus.tools import ToolDispatch
from chorus.tools.builtin import CreatePlanTool, LoadSkillTool, UpdateIntentStateTool


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
    intent_state = IntentStateService(IntentStateRepository(conn), session_svc)
    tool_dispatcher = ToolDispatch([
        CreatePlanTool(task_repo, content_repo, conn),
        LoadSkillTool(skill_loader),
        UpdateIntentStateTool(intent_state),
    ], _stub_settings())
    trace = TraceEmitter(trace_svc, tool_dispatcher, max_tokens=1024)
    hooks.register("TurnStart", emit_message_start, source="supervisor")
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Error", ErrorFinalizer(msg_svc).on_error)

    entry = stub_chat_model_provider(fake_client)
    loop = AgentLoop(hooks, tool_dispatcher, 1024)
    return SupervisorService(
        session_svc, msg_svc, skill_loader, hooks, entry,
        task_repo, tool_dispatcher, loop, intent_state,
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
    assert "task_plan_created" not in types_seq   # 不发此事件
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
    """Reply 型 tool_call 成对落库 + loop 继续到第二轮文本回复 done。

    锚定 OpenAI tool_calls/tool 配对约束：Reply 分支须先 append assistant(tool_calls=[call])
    再 append tool(result)，否则下一轮 build_provider_messages 回放孤儿 tool 消息。
    用真实 LoadSkillTool 加载不存在的技能名 → Reply("Error: skill '...' not found...")，
    下一轮模型回文本 done。
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
    # 历史：user + assistant(tool_calls) + tool + assistant(文本)
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
    """一轮内 ≥2 个 Reply 工具调用 → 收集后落一条 assistant 携带全部 tool_calls + N 条 tool 结果。

    锚定多 tool_call 配对结构，避免多 Reply 复用 message_id 撞表。下一轮模型回文本 done。
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
    # 无 error；正常结束 done
    assert "error" not in types_seq
    assert types_seq[-1] == "done"
    # 历史：user + assistant(2 tool_calls) + tool + tool + assistant(文本)
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool", "tool", "assistant"]
    assert len(msgs[1].tool_calls) == 2          # 第一条 assistant 携带两个 tool_call
    assert msgs[2].tool_call_id == "c1"          # 顺序保留
    assert msgs[3].tool_call_id == "c2"
    assert msgs[4].tool_calls == []              # 文本轮无 tool_call
    assert msgs[4].content == "两个技能都没找到"


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


def test_update_intent_state_does_not_finish():
    """非 ready_to_confirm 状态返 Reply 不杀轮次：文本+工具同轮 -> after_tools CONTINUE -> 下一轮纯文本 done。

    empty/capturing/needs_clarification 只记状态，终止权交还模型，须等下一轮模型纯文本走
    after_text 才 done。锚定非终止状态工具不替模型决定流程的契约；ready_to_confirm 终止另测。
    """
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    intent_args = {
        "intent_status": "empty",
        "goal": "闲聊",
        "known_slots": {},
        "missing_slots": [],
        "confirmation_summary": None,
    }
    # 第一轮：文本 + update_intent_state(Reply) → after_tools 无 Terminal → CONTINUE
    tool_stream = FakeStream([
        ({"content": "你好！"}, None),
        ({"tool_calls": [types.SimpleNamespace(
            index=0, id="c1", function=types.SimpleNamespace(
                name="update_intent_state", arguments=json.dumps(intent_args)))]}, "tool_calls"),
    ])
    # 第二轮：模型纯文本（不再调工具）→ after_text → done
    text_stream = FakeStream([({"content": "很高兴帮你"}, "stop")])
    client = FakeClient([tool_stream, text_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "你好"))
    types_seq = [e.type for e in events]
    # 两轮两个 message_start：工具不杀轮次，靠下一轮纯文本结束
    assert types_seq.count("message_start") == 2
    assert types_seq[-1] == "done"
    # 历史：user + assistant(文本+tool_calls) + tool + assistant(纯文本)
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool", "assistant"]
    assert msgs[1].content == "你好！"
    assert len(msgs[1].tool_calls) == 1
    assert msgs[1].tool_calls[0].name == "update_intent_state"
    assert msgs[2].role == "tool"
    assert msgs[2].tool_call_id == "c1"
    assert msgs[3].content == "很高兴帮你"
    assert (msgs[3].tool_calls or []) == []


def test_update_intent_state_ready_to_confirm_finishes():
    """ready_to_confirm 返 Terminal 杀轮次：单轮即 done，助手气泡取 friendly_reply。

    继 create_plan 之后第二个终止型工具。模型调 update_intent_state(ready_to_confirm) 后，
    after_tools 命中 Terminal -> FINISH -> 同轮 done，不再有后续纯文本轮。
    助手气泡 content 来自 friendly_reply 参数（模型本轮无正文），与 create_plan 同构。
    """
    conn, session_svc, msg_svc, trace_svc, task_repo, content_repo = _setup()
    intent_args = {
        "intent_status": "ready_to_confirm",
        "goal": "种草精品咖啡豆",
        "known_slots": {"主题": "精品咖啡豆"},
        "missing_slots": [],
        "confirmation_summary": {
            "title": "创作方向确认",
            "items": [{"label": "主题", "value": "精品咖啡豆"}],
        },
        "friendly_reply": "我整理了这次创作方向，请确认后开始",
    }
    tool_stream = FakeStream([({"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(
            name="update_intent_state", arguments=json.dumps(intent_args)))]}, "tool_calls")])
    client = FakeClient([tool_stream])
    sup = _build_supervisor(conn, session_svc, msg_svc, trace_svc, task_repo, content_repo, client)
    s = session_svc.create("test")
    events = list(sup.stream(s.id, "精品咖啡豆，轻松种草风格，3张图"))
    types_seq = [e.type for e in events]
    # 单轮一个 message_start：Terminal 即终止，无第二轮
    assert types_seq.count("message_start") == 1
    assert types_seq[-1] == "done"
    # 意图状态事件在 done 之前下发，驱动前端注入确认卡
    assert "intent_state" in types_seq
    # 历史：user + assistant(friendly_reply, tool_calls) + tool(占位)，无后续纯文本轮
    msgs = msg_svc.list_messages(s.id)
    assert [m.role for m in msgs] == ["user", "assistant", "tool"]
    assert msgs[1].content == "我整理了这次创作方向，请确认后开始"
    assert len(msgs[1].tool_calls) == 1
    assert msgs[1].tool_calls[0].name == "update_intent_state"
    assert msgs[2].role == "tool"
    assert msgs[2].tool_call_id == "c1"
    assert "等待用户拍板" in msgs[2].content


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
