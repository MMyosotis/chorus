"""SubAgentService.run smoke：ReAct + 产物解析 + 翻转待复核/完成。

覆盖自纠、协作式取消、最终产出轮漂移等场景。
"""
from __future__ import annotations

import tempfile
import types
from pathlib import Path

from chorus.agents.loop import AgentLoop
from chorus.agents.subagent import SubAgentService
from chorus.domain.session import Session
from chorus.domain.skill import SkillLoader
from chorus.domain.task import Task, TaskContent, TaskStatus
from chorus.domain.trace import ModelResponse, TracePhase
from chorus.hooks import HookRegistry, TraceEmitter
from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.trace import TraceService
from chorus.tests._helpers import stub_chat_model_provider
from chorus.tools import Tool, ToolDispatch


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


class SideEffectClient:
    """FakeClient 变体：每次调用先跑副作用再返对应流，供协作式取消/漂移用例模拟中途取消。"""

    def __init__(self, pairs):
        # pairs: list[(副作用函数 | None, stream)]
        self._pairs = list(pairs)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        side, stream = self._pairs.pop(0)
        if side is not None:
            side()
        return stream


class FakeTool(Tool):
    name = "baidu_search"
    description = "x"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments, ctx):
        from chorus.tools.framework import Reply
        return Reply("search-result")


def _setup():
    tmp = tempfile.mkdtemp()
    conn = ConnectionFactory(Path(tmp) / "t.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    content_repo = TaskContentRepository(conn)
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, trace_svc)
    return conn, msg_svc, trace_svc, task_repo, art_repo, content_repo


def _mk_task(task_repo, content_repo, agent_type="idea", status="running", deps=None):
    t = Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type=agent_type,
        status=status, dependencies=deps or [],
        created_at=0.0, updated_at=0.0,
    )
    task_repo.insert(t)
    content_repo.insert(TaskContent(task_id="t1", invoke_message="骨架：主题=测试"))
    return t


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, fake_client, aside=None):
    from chorus.repo.task_progress import TaskProgressRepository
    hooks = HookRegistry()
    tool_dispatcher = ToolDispatch([FakeTool()], _stub_settings())
    trace = TraceEmitter(trace_svc, tool_dispatcher, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)

    _provider = stub_chat_model_provider(fake_client)
    loop = AgentLoop(hooks, tool_dispatcher, 1024)
    if aside is None:
        aside = types.SimpleNamespace(generate=lambda agent_type, invoke: "")
    return SubAgentService(
        msg_svc, task_repo, art_repo, TaskProgressRepository(conn),
        content_repo, tool_dispatcher,
        _provider, loop, aside, SkillLoader(skills_dir=Path("/nonexistent-skills")),
    )


def _model_responses(trace_svc, task_id="t1"):
    """该 task 的模型响应 trace（每轮 ReAct 一条），按时间升序。"""
    return [
        t.payload for t in trace_svc.list_traces("s1")
        if t.task_id == task_id and t.phase is TracePhase.MODEL_RESPONSE
        and isinstance(t.payload, ModelResponse)
    ]


def test_subagent_idea_awaiting_confirm():
    """idea 子 Agent：无工具轮直接产出 → 翻转 running→awaiting_confirm + 写 artifacts。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    # 一轮文本回复（产出协议）
    content = "<!-- chorus:awaiting=y -->\n<!-- chorus:done=定了 -->\n\n### t\n- 视角：a\n- 理由：r"
    client = FakeClient([FakeStream([({"content": content}, "stop")])])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    art = art_repo.load("t1")
    assert art.artifacts.candidates[0].title == "t"
    assert art.narrative.done_line == "定了"
    mrs = _model_responses(trace_svc)
    assert len(mrs) == 1 and mrs[0].finish_reason == "stop"


def test_subagent_finalize_awaiting_confirm():
    """finalize 子 Agent：产出 PostCard → 翻转 running→awaiting_confirm（成品也需人工确认）。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "finalize", "running")
    content = "<!-- chorus:awaiting= -->\n<!-- chorus:done=汇总完成 -->\n\n# 夏日晚风\n\n一段\n\n#标签：#夏天"
    client = FakeClient([FakeStream([({"content": content}, "stop")])])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    assert art_repo.load("t1").artifacts.title == "夏日晚风"


def test_subagent_react_with_tool():
    """子 Agent 先调工具再产出：两轮 ReAct，trace 留两条 model_response。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    content = "<!-- chorus:awaiting=y -->\n<!-- chorus:done=z -->\n\n### t\n- 视角：a\n- 理由：r"
    # 第 1 轮工具调用，第 2 轮产出
    client = FakeClient([
        FakeStream([({"tool_calls": [types.SimpleNamespace(
            index=0, id="c1", function=types.SimpleNamespace(name="baidu_search", arguments="{}"))]}, "tool_calls")]),
        FakeStream([({"content": content}, "stop")]),
    ])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    mrs = _model_responses(trace_svc)
    assert len(mrs) == 2
    assert mrs[0].tool_calls[0].name == "baidu_search"
    assert mrs[1].finish_reason == "stop"


def test_subagent_failed_on_persistent_bad_output():
    """连续产物解析失败撞步数上限 → 翻转 running→failed。

    每轮坏产出喂回自纠，模型仍坏，撞步数上限才判死。
    """
    from chorus.agents.subagent import _MAX_STEPS
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    bad = "乱七八糟没有段"
    # 每轮都坏：_MAX_STEPS 轮后仍未产出 → failed
    streams = [FakeStream([({"content": bad}, "stop")]) for _ in range(_MAX_STEPS + 1)]
    client = FakeClient(streams)
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert content_repo.load("t1").error
    # 撞步数上限才判死：每轮都留 trace，共 _MAX_STEPS 条
    assert len(_model_responses(trace_svc)) == _MAX_STEPS


def test_subagent_self_corrects_on_bad_output():
    """首次解析错 → correction 喂回 → 模型重出正确产物 → awaiting_confirm。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    good = "<!-- chorus:awaiting=y -->\n<!-- chorus:done=定了 -->\n\n### t\n- 视角：a\n- 理由：r"
    # 第 1 轮坏产出，第 2 轮正确产出
    client = FakeClient([
        FakeStream([({"content": "乱七八糟没有段"}, "stop")]),
        FakeStream([({"content": good}, "stop")]),
    ])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    art = art_repo.load("t1")
    assert art.artifacts.candidates[0].title == "t"
    # 两轮 model_response trace（第 1 轮自纠 + 第 2 轮成功）
    assert len(_model_responses(trace_svc)) == 2


def _idea_content(done_line="DONE_MARKER"):
    """构造合法 idea 产出文本。"""
    return f"<!-- chorus:awaiting=y -->\n<!-- chorus:done={done_line} -->\n\n### t\n- 视角：a\n- 理由：r"


def _drift_to(task_repo, tid, to_status="pending"):
    def _side():
        task_repo.transition(tid, TaskStatus.RUNNING, to_status)
    return _side


def test_subagent_cooperative_cancel_between_iterations():
    """I-1：第 1 轮(工具调用)中途任务被僵死回收翻回待执行，第 2 轮迭代顶部复查到非运行即退出。
    即退出——不 _finalize、不 append done 气泡、不落 artifacts。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    tool_call_delta = {"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(name="baidu_search", arguments="{}"))]}
    # 第 1 轮：副作用漂移任务 + 工具调用流；第 2 轮：合法产出流（不应被消费）
    client = SideEffectClient([
        (_drift_to(task_repo, "t1"), FakeStream([(tool_call_delta, "tool_calls")])),
        (None, FakeStream([({"content": _idea_content("DONE_MARKER_I1")}, "stop")])),
    ])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    # 任务已漂移回待执行（_finalize 未成功 CAS 到 awaiting_confirm）
    assert task_repo.get("t1").status == TaskStatus.PENDING
    # 不落产物
    assert art_repo.load("t1") is None
    # 第 2 个脚本未消费——证明第 2 轮迭代在 _call_model 前就退出
    assert len(client._pairs) == 1
    # 无 done 气泡
    msgs = msg_svc.list_messages("s1")
    assert not any(getattr(m, "content", "") == "DONE_MARKER_I1" for m in msgs)


def test_subagent_finalize_drift_no_orphan():
    """I-2：最终产出轮的 _call_model 中途任务被僵死回收，_finalize 的 owning CAS
    (running→awaiting_confirm) 漂移失败：不 upsert 产物、不 append done 气泡。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, "idea", "running")
    # 单轮：副作用漂移任务 + 合法产出流；_finalize 的 CAS 必失败
    client = SideEffectClient([
        (_drift_to(task_repo, "t1"), FakeStream([({"content": _idea_content("DONE_MARKER_I2")}, "stop")])),
    ])
    sub = _build_subagent(conn, msg_svc, trace_svc, task_repo, art_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.PENDING
    # 不落产物（CAS 漂移→跳过 upsert）
    assert art_repo.load("t1") is None
    # 无 done 气泡
    msgs = msg_svc.list_messages("s1")
    assert not any(getattr(m, "content", "") == "DONE_MARKER_I2" for m in msgs)
    assert len(client._pairs) == 0  # 脚本已消费


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
