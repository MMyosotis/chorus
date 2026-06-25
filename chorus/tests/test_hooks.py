# kitty/tests/test_hooks.py
"""hooks 子系统 smoke test：ErrorFinalizer 异常收尾 + TraceEmitter 多来源传播 + TitlePostProcessor 收尾。

覆盖 ``kitty/hooks/``（此前无直接测试）：
- ErrorFinalizer.on_error：本轮已分配 message_id 时 append 一条 [Error] assistant 消息
  关闭本轮（不删数据——失败轮 assistant 本就未入库，库内天然干净）；未分配则跳过。
- TraceEmitter：before_model_request / on_tool_result 写 TraceEntry 并 yield TraceEvent；
  PF-B 验证 source/task_id 从 ctx 传播到持久化 TraceEntry（subagent 'subagent'+'t1'，
  默认 'supervisor'+None）。注：TraceEvent 本身不载 source/task_id，传播落点在 TraceEntry。
- TitlePostProcessor.on_stop：首轮 user/assistant 对生成标题，set_title_if_unset 未设则
  yield TitleUpdateEvent；已设 / generate 返 None 则 return None。

运行：.venv/bin/python -m kitty.tests.test_hooks
"""
from __future__ import annotations

import types

from chorus.agents import AgentContext
from chorus.domain.events import TitleUpdateEvent
from chorus.domain.trace import TracePhase
from chorus.hooks import ErrorFinalizer, TitlePostProcessor, TraceEmitter
from chorus.repositories.message import MessageRepository
from chorus.repositories.session import SessionRepository
from chorus.repositories.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)                                # "s1" 供异常收尾/trace（FK 父行）
    msg_svc = MessageService(MessageRepository(conn), TraceRepository(conn))
    session_svc = SessionService(SessionRepository(conn))
    return msg_svc, session_svc


# ---- ErrorFinalizer ----

def test_error_finalizer_appends_error_message_when_message_id_allocated():
    msg_svc, _ = _setup()
    msg_svc.append_user_message("s1", "hi")
    ctx = AgentContext(session_id="s1")
    ctx.turn.message_id = "m-err"
    ctx.outcome.exception = ValueError("boom")

    result = ErrorFinalizer(msg_svc).on_error(ctx)

    assert result is None                             # on_error 不 yield 事件
    msgs = msg_svc.list_messages("s1")
    assert len(msgs) == 2
    err = msgs[1]
    assert err.role == "assistant"
    assert err.id == "m-err"
    assert err.content == "[Error] boom"
    assert err.tool_calls == []


def test_error_finalizer_skips_when_message_id_not_allocated():
    msg_svc, _ = _setup()
    msg_svc.append_user_message("s1", "hi")
    ctx = AgentContext(session_id="s1")
    ctx.turn.message_id = ""                          # 异常发生在分配 message_id 之前
    ctx.outcome.exception = RuntimeError("early")

    result = ErrorFinalizer(msg_svc).on_error(ctx)

    assert result is None
    assert len(msg_svc.list_messages("s1")) == 1      # 未追加任何消息


# ---- TraceEmitter ----

def test_trace_propagates_subagent_source_and_task_id():
    msg_svc, _ = _setup()
    emitter = TraceEmitter(msg_svc, max_tokens=512)
    ctx = AgentContext(session_id="s1", source="subagent", task_id="t1")
    ctx.turn.message_id = "m1"
    ctx.turn.iteration_index = 2
    ctx.chat_model = "fake-model"

    events = list(emitter.before_model_request(ctx))

    assert len(events) == 1
    ev = events[0]
    assert ev.type == "trace"
    assert ev.phase is TracePhase.MODEL_REQUEST
    assert ev.iteration == 2
    assert ev.message_id == "m1"
    assert ev.payload["model"] == "fake-model"
    assert ev.payload["max_tokens"] == 512
    # PF-B：source/task_id 传播到持久化 TraceEntry（TraceEvent 本身不载这两个字段）
    entry = msg_svc.list_traces("s1")[0]
    assert entry.source == "subagent"
    assert entry.task_id == "t1"
    assert entry.message_id == "m1"


def test_trace_default_supervisor_when_ctx_unset():
    msg_svc, _ = _setup()
    emitter = TraceEmitter(msg_svc, max_tokens=256)
    ctx = AgentContext(session_id="s1")               # 默认 source="supervisor", task_id=None

    list(emitter.before_model_request(ctx))

    entry = msg_svc.list_traces("s1")[0]
    assert entry.source == "supervisor"
    assert entry.task_id is None


def test_trace_tool_result_payload_from_result_object():
    msg_svc, _ = _setup()
    emitter = TraceEmitter(msg_svc, max_tokens=256)
    ctx = AgentContext(session_id="s1", source="subagent", task_id="t1")
    ctx.turn.message_id = "m1"
    call = {"id": "call-1", "name": "search", "arguments": {"q": "x"}}
    result = types.SimpleNamespace(content="结果", duration_ms=42)

    events = list(emitter.on_tool_result(ctx, call, result))

    assert len(events) == 1
    ev = events[0]
    assert ev.phase is TracePhase.TOOL_RESULT
    assert ev.payload["tool_call_id"] == "call-1"
    assert ev.payload["name"] == "search"
    assert ev.payload["content"] == "结果"
    assert ev.payload["duration_ms"] == 42
    assert msg_svc.list_traces("s1")[0].source == "subagent"


# ---- TitlePostProcessor ----

class _StubTitleService:
    """替身 TitleGenerationService：只实现 generate(first_user, first_assistant)。"""

    def __init__(self, title):
        self._title = title
        self.calls = []

    def generate(self, first_user, first_assistant):
        self.calls.append((first_user, first_assistant))
        return self._title


def _seed_first_pair(msg_svc, sid):
    msg_svc.append_user_message(sid, "帮我写夏日博文")
    msg_svc.append_assistant_message(
        sid, message_id="m1", content="好的，这是一篇关于夏日的文字。", tool_calls=[])


def test_title_on_stop_yields_update_when_unset():
    msg_svc, session_svc = _setup()
    s = session_svc.create("新对话")
    _seed_first_pair(msg_svc, s.id)
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
    assert stub.calls == [("帮我写夏日博文", "好的，这是一篇关于夏日的文字。")]


def test_title_skips_when_already_set():
    msg_svc, session_svc = _setup()
    s = session_svc.create("新对话")
    session_svc.rename(s.id, "用户起的名")             # title_generated=True
    _seed_first_pair(msg_svc, s.id)
    stub = _StubTitleService("不该用")
    ctx = AgentContext(session_id=s.id)

    result = TitlePostProcessor(session_svc, msg_svc, stub).on_stop(ctx)

    assert result is None                              # set_title_if_unset 返 False → 跳过
    assert session_svc.get(s.id).title == "用户起的名"


def test_title_skips_when_generate_returns_none():
    msg_svc, session_svc = _setup()
    s = session_svc.create("新对话")
    _seed_first_pair(msg_svc, s.id)
    stub = _StubTitleService(None)
    ctx = AgentContext(session_id=s.id)

    result = TitlePostProcessor(session_svc, msg_svc, stub).on_stop(ctx)

    assert result is None
    assert session_svc.get(s.id).title == "新对话"
    assert session_svc.get(s.id).title_generated is False


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
