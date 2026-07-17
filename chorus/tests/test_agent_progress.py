"""子 agent 进度快照写入位点 + 运行租约终态门控。

进度快照一任务一行覆盖更新；四个终态写入点（入口、自纠、失败、汇总）拦截陈旧工作线程。
"""
from __future__ import annotations

import types
from pathlib import Path

from chorus.agents.loop import AgentLoop
from chorus.agents.subagent import SubAgentService, SubagentLoopStrategy, _MAX_STEPS
from chorus.domain.session import Session
from chorus.domain.skill import SkillLoader
from chorus.domain.task import AGENT_PROFILES, Task, TaskContent, TaskStatus
from chorus.hooks import HookRegistry, TraceEmitter
from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.trace import TraceService
from chorus.tests._helpers import stub_chat_model_provider
from chorus.tools import ToolCall, ToolDispatch
from chorus.tools.framework import DispatchResult, Reply


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
    conn = ConnectionFactory(Path("/tmp") / f"t_{__import__('time').time_ns()}.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    progress_repo = TaskProgressRepository(conn)
    content_repo = TaskContentRepository(conn)
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, trace_svc)
    return conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client, aside=None):
    hooks = HookRegistry()
    disp = ToolDispatch([], _stub_settings())
    trace = TraceEmitter(trace_svc, disp, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    loop = AgentLoop(hooks, disp, 1024)
    if aside is None:
        aside = types.SimpleNamespace(generate=lambda agent_type, invoke: "")
    return SubAgentService(
        msg_svc, task_repo, art_repo, progress_repo, content_repo,
        disp, stub_chat_model_provider(client), loop, aside,
        SkillLoader(skills_dir=Path("/nonexistent-skills")),
    )


def _mk_task(task_repo, content_repo, owner_id=100.0, status="running", agent_type="idea"):
    task = Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type=agent_type,
        status=status, dependencies=[],
        created_at=0.0, updated_at=0.0, owner_id=owner_id,
    )
    task_repo.insert(task)
    content_repo.insert(TaskContent(task_id="t1", invoke_message="骨架", progress_total=3))
    return task


def _idea_md(done_line="定了", awaiting_line="y"):
    """构造合法 idea 产出 markdown。"""
    return f"<!-- chorus:awaiting={awaiting_line} -->\n<!-- chorus:done={done_line} -->\n\n### t\n- 视角：a\n- 理由：r"


def _takeover(task_repo):
    """新 worker 抢占：僵死回收 + 重派，状态回 running 但归属漂移到 999。"""
    task_repo.transition("t1", TaskStatus.PENDING)
    task_repo.claim("t1", 999.0)


def test_progress_label_written_on_start():
    """入口租约通过即写创作量词；idea 一轮产出后量词仍在。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = FakeClient([FakeStream([({"content": _idea_md()}, "stop")])])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    progress = progress_repo.load("t1")
    assert progress is not None
    assert progress.composing_label == "个候选"
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM


def test_progress_retry_signal_on_bad_output():
    """首轮解析失败 -> 写自纠信号；次轮成功 -> 信号留存（汇总不覆写）。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = FakeClient([
        FakeStream([({"content": "乱七八糟没有段"}, "stop")]),
        FakeStream([({"content": _idea_md()}, "stop")]),
    ])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.AWAITING_CONFIRM
    assert progress_repo.load("t1").last_signal == "刚才格式没对齐，重新理一理"


def test_progress_fail_signal_on_exhausted():
    """连续坏产出撞步数上限 -> 写失败信号 + 翻 failed。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    bad = "乱七八糟没有段"
    streams = [FakeStream([({"content": bad}, "stop")]) for _ in range(_MAX_STEPS + 1)]
    client = FakeClient(streams)
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert progress_repo.load("t1").last_signal == "这步失败了"


def test_progress_fail_signal_on_exception():
    """模型调用抛异常 -> 写失败信号 + 翻 failed。"""
    def _boom():
        raise RuntimeError("model boom")

    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([(_boom, None)])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.FAILED
    assert progress_repo.load("t1").last_signal == "这步失败了"


def test_lease_drift_at_max_steps_skips_fail():
    """撞步数上限前归属漂移 -> 租约拦下失败写入：不翻 failed、不写失败信号。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    bad = "乱七八糟没有段"
    pairs = [(lambda: _takeover(task_repo), FakeStream([({"content": bad}, "stop")]))]
    pairs += [(None, FakeStream([({"content": bad}, "stop")])) for _ in range(_MAX_STEPS)]
    client = _SideClient(pairs)
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert progress_repo.load("t1").last_signal != "这步失败了"


def test_lease_takeover_prevents_stale_finalize():
    """汇总轮归属漂移 -> 租约拦下：不翻待复核、不落产物。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([
        (lambda: _takeover(task_repo), FakeStream([({"content": _idea_md()}, "stop")])),
    ])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert art_repo.load("t1") is None


def test_lease_takeover_prevents_stale_failed_on_exception():
    """异常轮归属漂移 -> 租约拦下失败写入：不翻 failed。"""
    def _takeover_and_boom():
        _takeover(task_repo)
        raise RuntimeError("model boom")

    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    client = _SideClient([(_takeover_and_boom, None)])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.RUNNING
    assert progress_repo.load("t1").last_signal != "这步失败了"


def test_finalize_drift_writes_no_terminal():
    """汇总轮被取消 -> 租约校验状态非 running 即早退：不落产物。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo)
    task_repo.transition("t1", "cancelled")
    # cancelled->pending 不合法，直接重置为 running 以便进入循环
    conn.get().execute("UPDATE tasks SET status='running', owner_id=100.0 WHERE id='t1'")

    def _cancel():
        task_repo.transition("t1", TaskStatus.CANCELLED)

    client = _SideClient([
        (_cancel, FakeStream([({"content": _idea_md(done_line="DONE_MARKER")}, "stop")])),
    ])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    assert task_repo.get("t1").status == TaskStatus.CANCELLED
    assert art_repo.load("t1") is None


def test_progress_chars_units_written_during_stream():
    """产出轮逐字累计 chars + 数 ### 行得 units,节流后落进度。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="idea")
    body = ("<!-- chorus:awaiting=y -->\n<!-- chorus:done=定了 -->\n\n"
            "### 候选一\n- 视角：a\n- 理由：r\n\n### 候选二\n- 视角：b\n- 理由：s")
    client = FakeClient([FakeStream([({"content": body}, "stop")])])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client)
    sub.run("t1")
    progress = progress_repo.load("t1")
    assert progress.composing_chars == len(body)
    assert progress.composing_units == 2


def test_image_after_dispatch_counts_units():
    """配图工具声明 units_produced,after_dispatch 累计,正文写字不覆盖。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="image")
    strategy = SubagentLoopStrategy(
        task=task_repo.get("t1"), progress_total=None, owner_id=100.0,
        profile=AGENT_PROFILES["image"], invoke="骨架",
        task_repo=task_repo, progress_repo=progress_repo,
        finalize=lambda *args: None, guarded_fail=lambda *args: None,
        skill_loader=SkillLoader(skills_dir=Path("/nonexistent-skills")),
        tool_names=("generate_image",), tool_dispatch=ToolDispatch([], _stub_settings()),
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
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="image")
    strategy = SubagentLoopStrategy(
        task=task_repo.get("t1"), progress_total=None, owner_id=100.0,
        profile=AGENT_PROFILES["image"], invoke="骨架",
        task_repo=task_repo, progress_repo=progress_repo,
        finalize=lambda *args: None, guarded_fail=lambda *args: None,
        skill_loader=SkillLoader(skills_dir=Path("/nonexistent-skills")),
        tool_names=("generate_image",), tool_dispatch=ToolDispatch([], _stub_settings()),
    )
    call = ToolCall(id="c1", name="baidu_search", arguments={"query": "咖啡"})
    progress_repo.set_composing_units("t1", 0)
    strategy.after_dispatch(call, DispatchResult(Reply("结果"), 10, activity_meta={"refs": []}))
    assert progress_repo.load("t1").composing_units == 0


def test_progress_aside_written_on_entry():
    """入口调旁白生成器,写进度 aside 字段。"""
    conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo = _setup()
    _mk_task(task_repo, content_repo, agent_type="idea")
    body = _idea_md(done_line="定了", awaiting_line="y")
    aside = types.SimpleNamespace(generate=lambda agent_type, invoke: "打算用光线串起一杯咖啡的时间")
    client = FakeClient([FakeStream([({"content": body}, "stop")])])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, progress_repo, content_repo, client, aside=aside)
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
