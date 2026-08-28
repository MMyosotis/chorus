"""子 agent 进度快照写入位点 + 运行租约终态门控。

进度快照一任务一行覆盖更新；四个终态写入点（入口、自纠、失败、汇总）拦截陈旧工作线程。
"""
from __future__ import annotations

import types
from pathlib import Path

from sqlalchemy import text

from chorus.agents.loop import AgentLoop
from chorus.agents.subagent import SubAgentService, SubagentLoopStrategy, _MAX_STEPS
from chorus.domain.memory import MemoryRecall
from chorus.domain.session import Session
from chorus.domain.skill import SkillLoader
from chorus.domain.task import AGENT_PROFILES, Task, TaskContent, TaskStatus
from chorus.hooks import HookRegistry, TraceEmitter
from chorus.repo.engine import build_engine
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.task_lease import LeaseGuard
from chorus.services.trace import TraceService
from chorus.tests._helpers import build_compact_service, stub_chat_model_provider, stub_memory_service
from chorus.tools import ToolCall, ToolDispatch
from chorus.tools.framework import DispatchResult, Reply


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [
            types.SimpleNamespace(choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)], usage=None)
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


class _SideClient(FakeClient):
    """每次调用先跑副作用再返对应流，供租约/漂移用例模拟中途抢占或抛错。"""

    def __init__(self, pairs):
        super().__init__([])
        self._pairs = list(pairs)

    def _create(self, **kwargs):
        side, stream = self._pairs.pop(0)
        if side is not None:
            side()
        return stream


def _setup():
    engine = build_engine(Path("/tmp") / f"t_{__import__('time').time_ns()}.db")
    SessionRepository(engine).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    msg_repo = MessageRepository(engine)
    trace_repo = TraceRepository(engine)
    task_repo = TaskRepository(engine)
    art_repo = TaskArtifactsRepository(engine)
    progress_repo = TaskProgressRepository(engine)
    content_repo = TaskContentRepository(engine)
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, ProviderMessageRepository(engine), trace_svc, build_compact_service(engine))
    return engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client, aside_gen=None):
    hooks = HookRegistry()
    disp = ToolDispatch([], _stub_settings())
    trace = TraceEmitter(trace_svc, disp)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    loop = AgentLoop(hooks, disp)
    if aside_gen is None:
        aside_gen = types.SimpleNamespace(generate=lambda agent_type, invoke: "")
    return SubAgentService(
        msg_svc, task_repo, art_repo, progress_repo, content_repo,
        disp, stub_chat_model_provider(client), loop, aside_gen,
        SkillLoader(skills_dir=Path("/nonexistent-skills")),
        stub_memory_service(),
        lease=LeaseGuard(task_repo, art_repo, content_repo, progress_repo),
    )


def _mk_task(task_repo, content_repo, owner_id=100.0, status="running", agent_type="idea"):
    task = Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type=agent_type,
        status=status, dependencies=[],
        created_at=0.0, updated_at=0.0, owner_id=owner_id,
    )
    task_repo.insert(task)
    content_repo.insert(TaskContent(task_id="t1", invoke_message="骨架"))
    return task


def _idea_md():
    """构造合法 idea 产出 markdown。"""
    return "### t\n- 视角：a\n- 理由：r"


def _image_md():
    """构造合法 image 产出 markdown：三张图,首张有 url、后两张留空(产物不全交 HIL)。"""
    return (
        "![街景](http://x/a.png)\n\n"
        "![人物]()\n\n"
        "![收尾]()"
    )


def _takeover(task_repo):
    """新 worker 抢占：僵死回收 + 重派，状态回 running 但归属漂移到 999。"""
    task_repo.transition("t1", TaskStatus.PENDING)
    task_repo.claim("t1", 999.0)


def test_progress_label_written_on_start():
    """入口租约通过即写创作量词；idea 一轮产出后量词仍在。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = FakeClient([FakeStream([({"content": _idea_md()}, "stop")])])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    progress = progress_repo.load("t1")
    assert progress is not None
    assert progress.composing_label == "个候选"
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM


def _tool_call_stream(call_id="c1"):
    """单轮工具调用流：调未知工具,Reply 喂回继续 loop,耗步数不产出。"""
    delta = {"tool_calls": [types.SimpleNamespace(
        index=0, id=call_id, function=types.SimpleNamespace(name="baidu_search", arguments="{}"))]}
    return FakeStream([(delta, "tool_calls")])


def test_progress_fail_signal_on_exhausted():
    """连续工具调用撞步数上限 -> 写失败信号 + 翻 failed。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    streams = [_tool_call_stream(f"c{i}") for i in range(_MAX_STEPS + 1)]
    client = FakeClient(streams)
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert progress_repo.load("t1").last_signal == "这步失败了"


def test_progress_fail_signal_on_exception():
    """模型调用抛异常 -> 写失败信号 + 翻 failed。"""
    def _boom():
        raise RuntimeError("model boom")

    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([(_boom, None)])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert progress_repo.load("t1").last_signal == "这步失败了"


def test_lease_drift_at_max_steps_skips_fail():
    """撞步数上限前归属漂移 -> 租约拦下失败写入：不翻 failed、不写失败信号。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    pairs = [(lambda: _takeover(task_repo), _tool_call_stream("c0"))]
    pairs += [(None, _tool_call_stream(f"c{i+1}")) for i in range(_MAX_STEPS)]
    client = _SideClient(pairs)
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert progress_repo.load("t1").last_signal != "这步失败了"


def test_lease_takeover_prevents_stale_finalize():
    """汇总轮归属漂移 -> 租约拦下：不翻待复核、不落产物。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([
        (lambda: _takeover(task_repo), FakeStream([({"content": _idea_md()}, "stop")])),
    ])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert art_repo.load("t1") is None


def test_lease_takeover_prevents_stale_failed_on_exception():
    """异常轮归属漂移 -> 租约拦下失败写入：不翻 failed。"""
    def _takeover_and_boom():
        _takeover(task_repo)
        raise RuntimeError("model boom")

    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([(_takeover_and_boom, None)])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert progress_repo.load("t1").last_signal != "这步失败了"


def test_finalize_drift_writes_no_terminal():
    """汇总轮被取消 -> 租约校验状态非 running 即早退：不落产物。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    task_repo.transition("t1", "cancelled")
    # cancelled->pending 不合法，直接重置为 running 以便进入循环
    with engine.begin() as db:
        db.execute(text("UPDATE tasks SET status='running', owner_id=100.0 WHERE id='t1'"))

    def _cancel():
        task_repo.transition("t1", TaskStatus.CANCELLED)

    client = _SideClient([
        (_cancel, FakeStream([({"content": _idea_md()}, "stop")])),
    ])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.CANCELLED
    assert art_repo.load("t1") is None


def test_progress_chars_units_written_during_stream():
    """产出轮逐字累计 chars + 数 ### 行得 units,节流后落进度。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="idea")
    body = ("### 候选一\n- 视角：a\n- 理由：r\n\n### 候选二\n- 视角：b\n- 理由：s")
    client = FakeClient([FakeStream([({"content": body}, "stop")])])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    progress = progress_repo.load("t1")
    assert progress.composing_chars == len(body)
    assert progress.composing_units == 2


def test_image_after_dispatch_counts_units():
    """配图工具声明 units_produced,after_dispatch 累计,正文写字不覆盖。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="image")
    strategy = SubagentLoopStrategy(
        task=task_repo.get("t1"), owner_id=100.0,
        profile=AGENT_PROFILES["image"], invoke="骨架",
        task_repo=task_repo, progress_repo=progress_repo,
        lease=types.SimpleNamespace(finalize=lambda *a: None, fail=lambda *a: None),
        skill_loader=SkillLoader(skills_dir=Path("/nonexistent-skills")),
        tool_names=("generate_image",), tool_dispatch=ToolDispatch([], _stub_settings()),
        memory=MemoryRecall(),
    )
    call = ToolCall(id="c1", name="generate_image", arguments={"prompt": "窗边咖啡"})
    strategy.after_dispatch(call, DispatchResult(Reply("http://x"), 10, units_produced=1))
    assert progress_repo.load("t1").composing_units == 1
    strategy.after_dispatch(call, DispatchResult(Reply("http://y"), 10, units_produced=1))
    assert progress_repo.load("t1").composing_units == 2
    progress_repo.set_composing_chars("t1", 200)
    assert progress_repo.load("t1").composing_units == 2


def test_tool_without_units_not_counted():
    """不带 units_produced 的工具(如搜索)不误增配图张数。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="image")
    strategy = SubagentLoopStrategy(
        task=task_repo.get("t1"), owner_id=100.0,
        profile=AGENT_PROFILES["image"], invoke="骨架",
        task_repo=task_repo, progress_repo=progress_repo,
        lease=types.SimpleNamespace(finalize=lambda *a: None, fail=lambda *a: None),
        skill_loader=SkillLoader(skills_dir=Path("/nonexistent-skills")),
        tool_names=("generate_image",), tool_dispatch=ToolDispatch([], _stub_settings()),
        memory=MemoryRecall(),
    )
    call = ToolCall(id="c1", name="baidu_search", arguments={"query": "咖啡"})
    progress_repo.set_composing_units("t1", 0)
    strategy.after_dispatch(call, DispatchResult(Reply("结果"), 10, activity_meta={"refs": []}))
    assert progress_repo.load("t1").composing_units == 0


def test_image_unfinished_still_finalizes_for_hil():
    """配图产物不全(无 url)不再代码判死,照常收尾交 HIL,成败交模型。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="image")
    client = FakeClient([FakeStream([({"content": _image_md()}, "stop")])])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    assert art_repo.load("t1") is not None


def test_progress_aside_written_on_entry():
    """入口调旁白生成器,写进度 aside 字段。"""
    engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="idea")
    body = _idea_md()
    aside_gen = types.SimpleNamespace(generate=lambda agent_type, invoke: "打算用光线串起一杯咖啡的时间")
    client = FakeClient([FakeStream([({"content": body}, "stop")])])
    sub = _build(engine, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client, aside_gen=aside_gen)
    sub.run("t1")
    assert progress_repo.load("t1").aside == "打算用光线串起一杯咖啡的时间"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
