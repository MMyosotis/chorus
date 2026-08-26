"""hooks 子系统 smoke：trace 多来源传播 + 标题收尾 + supervisor 异常占位。

覆盖 TraceEmitter 传播 source/task_id、TitlePostProcessor 首轮生成标题、
supervisor strategy on_error 补占位消息。
"""
from __future__ import annotations

import types

from chorus.agents import AgentContext
from chorus.agents.supervisor import SupervisorLoopStrategy
from chorus.domain.memory import MemoryRecall
from chorus.domain.skill import SkillLoader
from chorus.domain.events import TitleUpdateEvent
from chorus.domain.trace import TracePhase
from chorus.hooks import MemoryExtractor, TitlePostProcessor, TraceEmitter
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.trace import TraceService
from chorus.tests._helpers import build_compact_service, fresh_engine, seed_session


def _setup():
    engine = fresh_engine()
    seed_session(engine)                                # "s1" 供异常收尾/trace（FK 父行）
    trace_svc = TraceService(TraceRepository(engine))
    msg_svc = MessageService(MessageRepository(engine), ProviderMessageRepository(engine), trace_svc, build_compact_service(engine))
    session_svc = SessionService(SessionRepository(engine))
    return msg_svc, trace_svc, session_svc, engine


class _StubDispatcher:
    """TraceEmitter.on_tool_call 拉展示串用；本文件不测该路径，给个不爆的桩。"""

    def format_display(self, name, arguments):
        return name

    def running_label(self, name):
        return "工具调用中"


def test_supervisor_on_error_appends_error_message():
    msg_svc, trace_svc, _, engine = _setup()
    msg_svc.append_user_message("s1", "hi")
    strategy = SupervisorLoopStrategy("s1", msg_svc, None, None, None, SkillLoader(), (), MemoryRecall(), build_compact_service(engine))
    ctx = AgentContext(session_id="s1")
    ctx.turn.message_id = "m-err"
    ctx.outcome.exception = ValueError("boom")

    action = strategy.on_error(ctx, ValueError("boom"))

    msgs = msg_svc.list_messages("s1")
    assert len(msgs) == 2
    err = msgs[1]
    assert err.role == "assistant"
    assert err.id == "m-err"
    assert err.content == "[Error] boom"
    assert err.tool_calls == []
    events = list(action.events)
    assert len(events) == 1
    assert events[0].type == "error"
    assert events[0].content == "boom"


def test_trace_propagates_subagent_source_and_task_id():
    msg_svc, trace_svc, _, _ = _setup()
    emitter = TraceEmitter(trace_svc, _StubDispatcher())
    ctx = AgentContext(session_id="s1", source="subagent", task_id="t1")
    ctx.turn.message_id = "m1"
    ctx.chat_model = "fake-model"

    events = list(emitter.before_model_request(ctx))

    assert len(events) == 1
    ev = events[0]
    assert ev.type == "trace"
    assert ev.phase is TracePhase.MODEL_REQUEST
    assert ev.message_id == "m1"
    assert ev.payload["model"] == "fake-model"
    # source/task_id 传播到持久化 trace（事件本身不载这两个字段）
    entry = trace_svc.list_traces("s1")[0]
    assert entry.source == "subagent"
    assert entry.task_id == "t1"
    assert entry.message_id == "m1"


def test_trace_default_supervisor_when_ctx_unset():
    msg_svc, trace_svc, _, _ = _setup()
    emitter = TraceEmitter(trace_svc, _StubDispatcher())
    ctx = AgentContext(session_id="s1")               # 默认 source="supervisor", task_id=None
    ctx.chat_model = "fake-model"

    list(emitter.before_model_request(ctx))

    entry = trace_svc.list_traces("s1")[0]
    assert entry.source == "supervisor"
    assert entry.task_id is None


def test_trace_tool_result_payload_from_result_object():
    msg_svc, trace_svc, _, _ = _setup()
    emitter = TraceEmitter(trace_svc, _StubDispatcher())
    ctx = AgentContext(session_id="s1", source="subagent", task_id="t1")
    ctx.turn.message_id = "m1"
    call = {"id": "call-1", "name": "search", "arguments": {"q": "x"}}
    result = types.SimpleNamespace(
        outcome=types.SimpleNamespace(content="结果"), duration_ms=42,
    )

    events = list(emitter.on_tool_result(ctx, call, result))

    assert len(events) == 1
    ev = events[0]
    assert ev.phase is TracePhase.TOOL_RESULT
    assert ev.payload["tool_call_id"] == "call-1"
    assert ev.payload["name"] == "search"
    assert ev.payload["content"] == "结果"
    assert ev.payload["duration_ms"] == 42
    assert trace_svc.list_traces("s1")[0].source == "subagent"


class _StubTitleService:
    """替身 TitleGenerationService：只实现 generate(user_text)。"""

    def __init__(self, title):
        self._title = title
        self.calls = []

    def generate(self, user_text):
        self.calls.append(user_text)
        return self._title


def _seed_user_message(msg_svc, sid):
    msg_svc.append_user_message(sid, "帮我写夏日博文")


def test_title_on_stop_yields_update_when_unset():
    msg_svc, trace_svc, session_svc, _ = _setup()
    s = session_svc.create("新对话")
    _seed_user_message(msg_svc, s.id)
    stub = _StubTitleService("夏日晚风")
    ctx = AgentContext(session_id=s.id)

    result = TitlePostProcessor(session_svc, msg_svc, stub).on_stop(ctx)

    assert result is not None
    events = list(result)
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, TitleUpdateEvent)
    assert ev.id == s.id
    assert ev.title == "夏日晚风"
    got = session_svc.get(s.id)
    assert got.title == "夏日晚风"
    assert got.title_generated is True
    assert stub.calls == ["帮我写夏日博文"]


def test_title_skips_when_already_set():
    msg_svc, trace_svc, session_svc, _ = _setup()
    s = session_svc.create("新对话")
    session_svc.rename(s.id, "用户起的名")             # 标记为已生成
    _seed_user_message(msg_svc, s.id)
    stub = _StubTitleService("不该用")
    ctx = AgentContext(session_id=s.id)

    result = TitlePostProcessor(session_svc, msg_svc, stub).on_stop(ctx)

    assert result is None                              # 已定名短路 → 跳过
    assert stub.calls == []                            # 已定名不调 LLM
    assert session_svc.get(s.id).title == "用户起的名"


def test_title_skips_when_generate_returns_none():
    msg_svc, trace_svc, session_svc, _ = _setup()
    s = session_svc.create("新对话")
    _seed_user_message(msg_svc, s.id)
    stub = _StubTitleService(None)
    ctx = AgentContext(session_id=s.id)

    result = TitlePostProcessor(session_svc, msg_svc, stub).on_stop(ctx)

    assert result is None
    assert session_svc.get(s.id).title == "新对话"
    assert session_svc.get(s.id).title_generated is False


class _FakeMemoryExtract:
    """替身 MemoryService：只记录 extract 收到的会话 id。"""

    def __init__(self):
        self.extracted = []

    def extract(self, session_id):
        self.extracted.append(session_id)


def test_memory_extractor_on_stop_calls_extract():
    fake = _FakeMemoryExtract()
    ctx = AgentContext(session_id="s1")

    result = MemoryExtractor(fake).on_stop(ctx)

    assert result is None                       # 观测型 hook 不产事件
    assert fake.extracted == ["s1"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
