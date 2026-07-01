"""SubAgentService 写 task_activities 的顺序契约 + 运行租约 + done_images 累计。

运行：``.venv/bin/python -m chorus.tests.test_agent_activities``

偏离 brief 说明（brief 自身两处冲突，TDD 自纠）：
1. done_images 累计顺序：brief 的 _exec_tools 在调 tool_done_activity **前** append 当前
   url，但 Task B 已提交的 _image_done 做 ``all_images = done_images + [url]``（约定
   done_images 不含当前 url）——brief 字面顺序会双计，得 [2,3,4] 而 brief 测试断言 [1,2,3]。
   实现改为 **先调 tool_done_activity 再 append**（对齐 Task B 契约 + 命中 [1,2,3]）。
2. 租约早退测试：brief 的 test_lease_expired_worker_writes_no_activity 在 sub.run **前**
   把 started_at 重 CAS 成 999，期望 entry 租约校验触发早退。但 _run_loop 进入时重新 load
   task（started_at=999），捕获 run_started_at=999，entry _lease_valid 重读也是 999 → 有效
   → 仍写 started。entry 校验是多线程竞态护栏（entry-load 与 lease-check 相邻同读一份 DB，
   单线程无法插入漂移），故改为测 max-steps 路径的租约早退——同样验证"漂移即不写终态活动"。
"""
from __future__ import annotations

import json
import types
from pathlib import Path

from chorus.agents.subagent import SubAgentService
from chorus.domain.session import Session
from chorus.domain.task import TaskStatus
from chorus.hooks import HookRegistry, TraceEmitter
from chorus.repo.connection import ConnectionFactory
from chorus.repo.message import MessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_steps import TaskStepsRepository
from chorus.repo.trace import TraceRepository
from chorus.services.message import MessageService
from chorus.services.trace import TraceService
from chorus.tests._helpers import stub_chat_model_provider
from chorus.tools import Tool, ToolDispatch
from chorus.tools.framework import Reply, ToolRunResult


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
    """FakeClient 变体：每次 create 先跑 side_effect(可空) 再返对应 stream。

    供租约/漂移用例——在 _call_model 内改任务态/started_at，模拟中途抢占。
    """

    def __init__(self, pairs):
        # pairs: list[(side_effect_fn | None, stream)]
        super().__init__([])  # _scripts 不用，走 _pairs
        self._pairs = list(pairs)

    def _create(self, **kwargs):
        side, stream = self._pairs.pop(0)
        if side is not None:
            side()
        return stream


class FakeImageTool(Tool):
    """每次 run 返一张图的 ToolRunResult，模拟 generate_image 逐张出图。"""
    name = "generate_image"
    description = "x"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, urls):
        self._urls = list(urls)
        self._i = 0

    def run(self, arguments, ctx):
        url = self._urls[self._i % len(self._urls)]
        self._i += 1
        return ToolRunResult(Reply(url), activity_meta={"url": url})


def _setup():
    conn = ConnectionFactory(Path("/tmp") / f"t_{__import__('time').time_ns()}.db")
    SessionRepository(conn).insert(Session(id="s1", title="t", title_generated=False, created_at=0.0, updated_at=0.0))
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    steps_repo = TaskStepsRepository(conn)
    act_repo = TaskActivitiesRepository(conn)
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, trace_svc)
    return conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, tools):
    hooks = HookRegistry()
    trace = TraceEmitter(trace_svc, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    disp = ToolDispatch(tools, _stub_settings())
    return SubAgentService(
        conn, msg_svc, task_repo, art_repo, steps_repo, act_repo,
        disp, hooks, stub_chat_model_provider(client), 1024,
    )


def _mk_image_task(task_repo, started_at=100.0, status="running", agent_type="image"):
    from chorus.domain.task import Task
    t = Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type=agent_type,
        status=status, invoke_message="骨架", dependencies=[],
        created_at=0.0, updated_at=0.0, started_at=started_at,
        metadata={"goal": "生成 3 张配图", "progress_total": 3, "progress_unit": "张图"},
    )
    task_repo.insert(t)
    return t


def _image_artifacts(n=3):
    """合法 image 产出（n 张图）+ narrative。"""
    artifacts = {"images": [{"url": f"http://x/{i}.jpg", "caption": ""} for i in range(n)]}
    narrative = {"awaiting_line": "图好了", "done_line": "配图完成"}
    return artifacts, narrative


def _content(artifacts, narrative):
    return (
        f"<<<ARTIFACTS:json>>>\n{json.dumps(artifacts)}\n<<<ARTIFACTS_END>>>\n"
        f"<<<NARRATIVE:json>>>\n{json.dumps(narrative)}\n<<<NARRATIVE_END>>>"
    )


def test_started_and_awaiting_activities_written():
    """idea 一轮产出 → started + awaiting_confirm 两条 activity，且 started 在前。"""
    from chorus.domain.task import Task
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", invoke_message="x", dependencies=[],
        created_at=0.0, updated_at=0.0, started_at=100.0,
    ))
    artifacts = {"candidates": [{"index": 0, "title": "t", "angle": "a", "reason": "r"}], "selected": None}
    narrative = {"awaiting_line": "y", "done_line": "定了"}
    client = FakeClient([FakeStream([({"content": _content(artifacts, narrative)}, "stop")])])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    types_seq = [a.event_type for a in acts]
    assert "started" in types_seq
    assert "awaiting_confirm" in types_seq
    assert types_seq.index("started") < types_seq.index("awaiting_confirm")


def test_generate_image_writes_progressive_tool_done_activities():
    """image 子 Agent 连续 3 次 generate_image → 3 条独立 tool_done activity（1/3 2/3 3/3）。

    顺序契约：started → tool_started → tool_done → ... → awaiting_confirm。
    """
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    _mk_image_task(task_repo)
    artifacts, narrative = _image_artifacts(3)
    tool_delta = {"tool_calls": [types.SimpleNamespace(
        index=0, id="c1", function=types.SimpleNamespace(name="generate_image", arguments="{}"))]}
    # 3 轮工具调用 + 1 轮产出
    client = FakeClient([
        FakeStream([(tool_delta, "tool_calls")]),
        FakeStream([(tool_delta, "tool_calls")]),
        FakeStream([(tool_delta, "tool_calls")]),
        FakeStream([({"content": _content(artifacts, narrative)}, "stop")]),
    ])
    tool = FakeImageTool(["http://x/1.jpg", "http://x/2.jpg", "http://x/3.jpg"])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [tool])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    types_seq = [a.event_type for a in acts]
    tool_done = [a for a in acts if a.event_type == "tool_done"]
    assert len(tool_done) == 3  # 三条独立，不 update
    # 进度递进：current 1 → 2 → 3
    currents = [a.progress_json["current"] for a in tool_done if a.progress_json]
    assert currents == [1, 2, 3]
    assert tool_done[-1].progress_json["total"] == 3
    # 顺序契约：started 最先；每组 tool_started 在 tool_done 前；awaiting_confirm 最后
    assert types_seq[0] == "started"
    assert types_seq.index("tool_started") < types_seq.index("tool_done")
    assert types_seq.index("tool_done") < types_seq.index("awaiting_confirm")
    # 最终 awaiting_confirm（image 需复核）
    assert any(a.event_type == "awaiting_confirm" for a in acts)


def test_lease_drift_at_max_steps_skips_failed_activity():
    """运行租约（max-steps 路径）：撞 _MAX_STEPS 前任务被新 worker 抢占（started_at 漂移），
    旧 worker 的 max-steps 路径租约校验失败 → 不 CAS failed、不写 failed activity。

    entry 租约校验是多线程竞态护栏（entry-load 与 lease-check 相邻同读一份 DB，单线程
    无法插入漂移），故此处测 max-steps 路径的租约早退——同样验证"漂移即不写终态活动"。
    """
    from chorus.agents.subagent import _MAX_STEPS
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    _mk_image_task(task_repo, started_at=100.0, agent_type="idea")
    bad = "乱七八糟没有段"

    def _takeover():
        # 模拟新 worker 抢占：zombie 回收 (running→pending) + 重派 (pending→running, started_at=999)
        task_repo.cas_update("t1", TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
        task_repo.cas_update("t1", TaskStatus.PENDING.value, TaskStatus.RUNNING.value, started_at=999.0)

    # 第 1 轮触发抢占 + 坏产出；后续坏产出撞 max-steps
    pairs = [(_takeover, FakeStream([({"content": bad}, "stop")]))]
    pairs += [(None, FakeStream([({"content": bad}, "stop")])) for _ in range(_MAX_STEPS)]
    client = _SideClient(pairs)
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    # 租约漂移 → max-steps 路径不写 failed
    assert not any(a.event_type == "failed" for a in acts), \
        f"租约漂移后不应写 failed activity，实际: {[a.event_type for a in acts]}"
    # 任务仍 running（旧 worker 无权 CAS 新 worker 的 task 到 failed）
    assert task_repo.get("t1").status == TaskStatus.RUNNING.value


def test_lease_takeover_prevents_stale_finalize():
    """运行租约（_finalize 路径，核心场景）：产出轮 _call_model 中途任务被新 worker 抢占
    （zombie 回收 + 重派，status 仍 running 但 started_at 漂移到 999）。旧 worker 的
    _finalize 租约校验失败 → 不 CAS awaiting、不 upsert 产物、不写 awaiting activity。

    这是租约存在的核心理由——CAS 单独会成功（status 仍 running），从而偷走新 worker 的
    task；租约用 started_at 区分新旧 worker，旧 worker 早退不污染。
    """
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    _mk_image_task(task_repo, started_at=100.0, agent_type="idea")
    artifacts = {"candidates": [{"index": 0, "title": "t", "angle": "a", "reason": "r"}], "selected": None}
    narrative = {"awaiting_line": "y", "done_line": "定了"}

    def _takeover():
        # 新 worker 抢占：zombie 回收 (running→pending) + 重派 (pending→running, started_at=999)
        task_repo.cas_update("t1", TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
        task_repo.cas_update("t1", TaskStatus.PENDING.value, TaskStatus.RUNNING.value, started_at=999.0)

    client = _SideClient([
        (_takeover, FakeStream([({"content": _content(artifacts, narrative)}, "stop")])),
    ])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    # 旧 worker 租约失效 → 不写 awaiting_confirm（CAS 单独会成功，租约拦下）
    assert not any(a.event_type == "awaiting_confirm" for a in acts), \
        f"租约漂移后不应写 awaiting activity，实际: {[a.event_type for a in acts]}"
    # 不 upsert 产物（不偷新 worker 的 task）
    assert art_repo.load("t1") is None
    # 任务仍 running（新 worker 持有，旧 worker 无权 CAS 到 awaiting）
    assert task_repo.get("t1").status == TaskStatus.RUNNING.value


def test_lease_takeover_prevents_stale_failed_on_exception():
    """运行租约（run-except 路径）：_call_model 抛异常时任务已被新 worker 抢占
    （zombie 回收 + 重派，status 仍 running 但 started_at 漂移到 999）。旧 worker 的
    run-except 租约校验失败 → 不 CAS failed、不写 failed activity。

    run-except 是 subagent 终态 CAS 唯一未租约门控的位点——CAS 单独会成功（status 仍
    running），从而偷走新 worker 的 task 到 failed 并写伪 failed activity；租约用
    started_at 区分新旧 worker，旧 worker 早退不污染。与 _finalize 路径对称。
    """
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    _mk_image_task(task_repo, started_at=100.0, agent_type="idea")

    def _takeover_and_boom():
        # 新 worker 抢占：zombie 回收 (running→pending) + 重派 (pending→running, started_at=999)
        task_repo.cas_update("t1", TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
        task_repo.cas_update("t1", TaskStatus.PENDING.value, TaskStatus.RUNNING.value, started_at=999.0)
        # 旧 worker 的网络调用随后抛异常（触发 run 的 except）
        raise RuntimeError("model boom")

    # _SideClient: side 先跑（takeover+raise），stream 永远不会被用到
    client = _SideClient([(_takeover_and_boom, None)])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    # 旧 worker 租约失效 → 不写 failed（CAS 单独会成功，租约拦下）
    assert not any(a.event_type == "failed" for a in acts), \
        f"租约漂移后不应写 failed activity，实际: {[a.event_type for a in acts]}"
    # 任务仍 running（新 worker 持有，旧 worker 无权 CAS 到 failed）
    assert task_repo.get("t1").status == TaskStatus.RUNNING.value


def test_finalize_drift_writes_no_done_activity():
    """CAS 漂移（被 cancel）→ 不写 done/awaiting activity（与现有 I-2 一致）。"""
    from chorus.domain.task import Task
    conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo = _setup()
    _mk_image_task(task_repo, started_at=100.0, agent_type="idea")
    artifacts = {"candidates": [{"index": 0, "title": "t", "angle": "a", "reason": "r"}], "selected": None}
    narrative = {"awaiting_line": "y", "done_line": "DONE_MARKER"}
    # 单轮：副作用取消任务 + 合法产出流；_finalize CAS 必失败
    task_repo.cas_update("t1", "running", "cancelled")
    # cancelled→pending 不合法（CAS 返 False 不动），用直接 SQL 重置为 running 以便 _run_loop 进入
    conn.get().execute("UPDATE tasks SET status='running', started_at=100.0 WHERE id='t1'")

    def _cancel():
        task_repo.cas_update("t1", TaskStatus.RUNNING.value, TaskStatus.CANCELLED.value)

    client = _SideClient([
        (_cancel, FakeStream([({"content": _content(artifacts, narrative)}, "stop")])),
    ])
    sub = _build(conn, msg_svc, trace_svc, task_repo, art_repo, steps_repo, act_repo, client, [])
    sub.run("t1")
    acts = act_repo.list_by_task("t1")
    # 不写 done/awaiting（finalize 漂移：lease 校验 status≠running 即早退，CAS 不会成功）
    assert not any(a.event_type in ("done", "awaiting_confirm") for a in acts)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
