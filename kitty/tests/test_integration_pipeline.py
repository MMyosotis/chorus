# kitty/tests/test_integration_pipeline.py
"""多智能体端到端 4 链路 smoke：supervisor 建图 → subagent awaiting_confirm → confirm finished → scheduler 派发 finalize。

此前端到端 smoke 仅存于 /tmp 一次性脚本（task-9 brief Step 3），且该脚本有 3 处内联 bug
（见下）。本文件修正后入库为常驻防线。FakeClient 模拟 LLM，不经真实 API / HTTP；scheduler
仅手调一次 ``_tick()``（不起后台线程），其派发的 finalize worker 是唯一异步点，用轮询等其落定。

task-9 脚本 3 处 bug（本文件已修正）：
1. hook 事件名↔方法名映射错：脚本用 ``getattr(t, e)``（e 为 "PreToolUse" 等大驼峰事件名），
   但 ``TraceEmitter`` 的方法是 snake_case 且非简单同名——正确映射是
   ``PreToolUse→on_tool_call``、``PostToolUse→on_tool_result``。
2. subagent 的 chat_models 未包 ``ChatModelEntry``：脚本传 ``{'m': sub_client}``（裸 FakeClient），
   而 ``SubAgentService`` 取 ``entry.client`` / ``entry.model_id``，裸 client 无 model_id。
3. 调用了不存在的 repo 方法（原 /tmp 脚本的 ``list_by_session``）：正确方法是
   ``find_by_session_statuses`` / ``find_pending_with_deps``（已对照 repositories/task.py 核实）。

4 条链路（任一断裂即测试失败）：
1. ``supervisor.stream`` 产出 ``task_plan_created`` + 落库 2 个 active task（idea + finalize）。
2. CAS idea pending→running 后 ``subagent.run`` → idea awaiting_confirm + 写 artifacts。
3. ``TaskService.confirm(idea, selected=0)`` → idea finished。
4. ``scheduler._tick`` 派发 finalize（idea 已 finished 解除 dep 阻塞）→ finalize finished（产出 PostCard）。

运行：.venv/bin/python -m kitty.tests.test_integration_pipeline
"""
from __future__ import annotations

import json
import tempfile
import time
import types
from pathlib import Path

from kitty.agents.scheduler import TaskScheduler
from kitty.agents.subagent import SubAgentService
from kitty.agents.supervisor import ChatModelEntry, SupervisorService
from kitty.domain.skill import SkillLoader
from kitty.domain.task import ACTIVE_STATUSES, TaskStatus, can_schedule
from kitty.hooks import ErrorFinalizer, HookRegistry, TraceEmitter
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.task import TaskRepository
from kitty.repositories.task_artifacts import TaskArtifactsRepository
from kitty.repositories.task_steps import TaskStepsRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.services.task import TaskService
from kitty.tools import ToolContext, ToolRegistry


# —— FakeClient / FakeStream（与 test_agent_supervisor / test_agent_subagent 同模式）——


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)]
            )
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


def _wrap_sections(artifacts, narrative) -> str:
    return (
        f"<<<ARTIFACTS:json>>>\n{json.dumps(artifacts, ensure_ascii=False)}\n<<<ARTIFACTS_END>>>\n"
        f"<<<NARRATIVE:json>>>\n{json.dumps(narrative, ensure_ascii=False)}\n<<<NARRATIVE_END>>>"
    )


def _idea_content() -> str:
    artifacts = {
        "candidates": [{"index": 0, "title": "夏日晚风", "angle": "清凉", "reason": "应季"}],
        "selected": None,
    }
    narrative = {"busy_lines": ["翻翻热点"], "awaiting_line": "等你挑一个", "done_line": "选题定了"}
    return _wrap_sections(artifacts, narrative)


def _finalize_content() -> str:
    # PostCard 结构（parse_output 对 finalize 强校验整棵 PostCard）
    card = {
        "title": "夏日晚风",
        "cover": {"url": "http://x/a.jpg"},
        "sections": [{"kind": "paragraph", "text": "蝉鸣与晚风。"}],
        "tags": ["#夏天"],
        "summary": "一篇夏日博文",
    }
    narrative = {"busy_lines": ["组装中"], "awaiting_line": "", "done_line": "成品出炉"}
    return _wrap_sections(card, narrative)


def _plan_args() -> dict:
    return {
        "thought": "想了一下",
        "friendly_reply": "好的，开始为你创作",
        "intent": {"topic": "夏日博文", "style": "轻松", "image_count": 2},
        "steps": [
            {"agent_type": "idea", "deps": [], "focus": "选题"},
            {"agent_type": "finalize", "deps": [0], "focus": "汇总成文"},
        ],
    }


def _build_assembly():
    """装配全链路组件到临时 DB。返回 (supervisor, subagent, task_service, scheduler, task_repo, session_svc)。"""
    conn = ConnectionFactory(Path(tempfile.mkdtemp()) / "t.db")
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    task_repo = TaskRepository(conn)
    art_repo = TaskArtifactsRepository(conn)
    steps_repo = TaskStepsRepository(conn)

    session_svc = SessionService(session_repo)
    msg_svc = MessageService(msg_repo, trace_repo)

    # 扁平 hook 注册表：4 个 trace 观测点 + Error 恢复（修正 bug 1：显式 snake_case 方法名映射）
    hooks = HookRegistry()
    trace = TraceEmitter(msg_svc, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Error", ErrorFinalizer(msg_svc).on_error)

    skill_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
    skill_loader.load()
    tool_registry = ToolRegistry([])

    def tool_ctx_factory(session_id, image_model=None):
        return ToolContext(skill_loader=None, session_id=session_id, image_model=image_model)

    # supervisor：一次 create_plan tool_call 流
    sup_client = FakeClient([FakeStream([
        ({"tool_calls": [types.SimpleNamespace(
            index=0, id="c1", function=types.SimpleNamespace(
                name="create_plan", arguments=json.dumps(_plan_args(), ensure_ascii=False))
        )]}, "tool_calls"),
    ])])
    sup_entry = ChatModelEntry(client=sup_client, model_id="fake")
    supervisor = SupervisorService(
        session_svc, msg_svc, skill_loader, hooks, {"fake": sup_entry},
        "fake", 1024, task_repo, conn,
    )

    # subagent：idea + finalize 两轮产出按执行顺序入队（共享同一 FakeClient 队列）。
    # 修正 bug 2：chat_models 的值必须包成 ChatModelEntry（entry.client / entry.model_id）。
    # 入队两轮避免 task-9 脚本的「finalize 复用空队列→failed」fake 限制，让链路 4 真正跑通到 finished。
    sub_client = FakeClient([
        FakeStream([({"content": _idea_content()}, "stop")]),
        FakeStream([({"content": _finalize_content()}, "stop")]),
    ])
    sub_entry = ChatModelEntry(client=sub_client, model_id="fake")
    subagent = SubAgentService(
        conn, msg_svc, task_repo, art_repo, steps_repo,
        tool_registry, tool_ctx_factory, hooks,
        {"fake": sub_entry}, {"idea": "fake", "finalize": "fake"},
        1024, tool_registry.schemas_openai(),
    )

    task_service = TaskService(task_repo, art_repo, steps_repo, session_svc)
    scheduler = TaskScheduler(
        task_repo, trace_repo, subagent.run, session_svc,
        interval=0.01, zombie_timeout=999, pool_size=2,
    )
    return supervisor, subagent, task_service, scheduler, task_repo, session_svc


def test_end_to_end_pipeline():
    """4 链路全跑通：supervisor 建图 → idea awaiting_confirm → confirm finished → scheduler 派发 finalize。"""
    sup, sub, task_service, scheduler, task_repo, session_svc = _build_assembly()
    session = session_svc.create("集成测试")
    sid = session.id

    # —— 链路 1：supervisor 建图 ——
    events = list(sup.stream(sid, "帮我写一篇夏日博文"))
    assert any(e.type == "task_plan_created" for e in events), \
        f"缺 task_plan_created，事件序列: {[e.type for e in events]}"
    assert task_repo.count_by_session_statuses(sid, ACTIVE_STATUSES) == 2

    # 修正 bug 3：用真实存在的 find_by_session_statuses（非 list_by_session）
    tasks = task_repo.find_by_session_statuses(sid, ACTIVE_STATUSES)
    idea = next(t for t in tasks if t.agent_type == "idea")
    finalize = next(t for t in tasks if t.agent_type == "finalize")
    assert idea.id in finalize.dependencies  # finalize 依赖 idea

    # —— 链路 2：subagent 跑 idea → awaiting_confirm ——
    # 手动 CAS pending→running（不走 scheduler，保持链路 2/4 的时序可控）
    assert task_repo.cas_update(idea.id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
    sub.run(idea.id)
    assert task_repo.get(idea.id).status == TaskStatus.AWAITING_CONFIRM.value

    # confirm 前：finalize 仍被 dep 阻塞（idea awaiting_confirm ≠ finished）
    assert not can_schedule(finalize, [task_repo.get(idea.id)])

    # —— 链路 3：confirm idea → finished ——
    task_service.confirm(idea.id, selected=0)
    assert task_repo.get(idea.id).status == TaskStatus.FINISHED.value

    # —— 链路 4：scheduler 派发 finalize（dep 已解除）——
    assert can_schedule(finalize, [task_repo.get(idea.id)])  # 现在可调度
    scheduler._tick()  # CAS pending→running + spawn worker 线程跑 subagent.run(finalize)

    # finalize 由 worker 线程异步跑；轮询等其离开 pending/running（WAL 跨线程可见）。
    # 因 idea+finalize 两轮 fake 流均已入队，无空队列限制，finalize 应达 finished。
    # 宽松下限（注释）：finalize 至少不再 pending-with-unmet-dep，即已 running/awaiting/finished/failed；
    # 此处取强断言 finished，任一链路断裂都会以实际状态暴露。
    deadline = time.time() + 2.0
    fin = task_repo.get(finalize.id)
    while fin.status in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value) and time.time() < deadline:
        time.sleep(0.02)
        fin = task_repo.get(finalize.id)
    assert fin.status == TaskStatus.FINISHED.value, f"finalize 链路未达 finished，实际: {fin.status}"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
