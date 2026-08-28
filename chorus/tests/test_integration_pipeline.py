"""多智能体端到端 4 链路 smoke：建图 → 子 agent 待复核 → 确认完成 → 派发汇总成品。

FakeClient 模拟 LLM，不经真实 API / HTTP；scheduler 仅手调一次，其派发的汇总 worker 是唯一异步点。
"""
from __future__ import annotations

import json
import tempfile
import time
import types
from pathlib import Path

from chorus.agents.loop import AgentLoop
from chorus.agents.scheduler import TaskScheduler
from chorus.agents.subagent import SubAgentService
from chorus.agents.supervisor import SupervisorService
from chorus.domain.skill import SkillLoader
from chorus.domain.task import ACTIVE_STATUSES, TaskStatus
from chorus.hooks import HookRegistry, TraceEmitter
from chorus.repo.engine import build_engine
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.trace import TraceRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.services.task_lease import LeaseGuard
from chorus.services.trace import TraceService
from chorus.tests._helpers import build_compact_service, stub_chat_model_provider, stub_memory_service
from chorus.tools import ToolDispatch
from chorus.tools.builtin import CreatePlanTool


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)], usage=None
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


def _idea_content() -> str:
    return "### 夏日晚风\n- 视角：清凉\n- 理由：应季"


def _finalize_content() -> str:
    return ("---\n"
            "title: 夏日晚风\n"
            "preview_ref: web-blog/preview/desktop.html\n"
            "stylesheet_ref: web-blog/preview/desktop.css\n"
            "summary: 蝉鸣与晚风\ntags: [夏天]\n"
            "---\n\n蝉鸣与晚风。")


def _plan_args() -> dict:
    return {
        "thought": "想了一下",
        "intent": {"topic": "夏日博文", "style": "轻松", "image_count": 2},
        "steps": [
            {"agent_type": "idea", "deps": []},
            {"agent_type": "finalize", "deps": [0]},
        ],
    }


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def _build_assembly():
    """装配全链路组件到临时 DB。返回 (supervisor, subagent, task_service, scheduler, task_repo, session_svc)。"""
    engine = build_engine(Path(tempfile.mkdtemp()) / "t.db")
    session_repo = SessionRepository(engine)
    msg_repo = MessageRepository(engine)
    trace_repo = TraceRepository(engine)
    task_repo = TaskRepository(engine)
    art_repo = TaskArtifactsRepository(engine)
    content_repo = TaskContentRepository(engine)

    session_svc = SessionService(session_repo)
    trace_svc = TraceService(trace_repo)
    msg_svc = MessageService(msg_repo, ProviderMessageRepository(engine), trace_svc, build_compact_service(engine))

    # 扁平 hook 注册表：4 个 trace 观测点
    hooks = HookRegistry()
    skill_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
    intent_state = IntentStateService(IntentStateRepository(engine), IntentConfirmationRepository(engine), session_svc)
    tool_dispatcher = ToolDispatch([CreatePlanTool(task_repo, content_repo, intent_state)], _stub_settings())
    trace = TraceEmitter(trace_svc, tool_dispatcher)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)

    agent_loop = AgentLoop(hooks, tool_dispatcher)

    task_service = TaskService(
        task_repo, art_repo, TaskProgressRepository(engine), content_repo, session_svc,
        stub_memory_service(),
    )

    # supervisor：一次建图工具调用流
    sup_client = FakeClient([FakeStream([
        ({"tool_calls": [types.SimpleNamespace(
            index=0, id="c1", function=types.SimpleNamespace(
                name="create_plan", arguments=json.dumps(_plan_args(), ensure_ascii=False))
        )]}, "tool_calls"),
    ])])
    supervisor = SupervisorService(
        session_svc, msg_svc, hooks,
        stub_chat_model_provider(sup_client), task_service, tool_dispatcher, agent_loop,
        intent_state, skill_loader,
        stub_memory_service(), build_compact_service(engine),
    )

    # subagent：选题 + 汇总两轮产出按执行顺序入队（共享同一 FakeClient 队列）。
    sub_client = FakeClient([
        FakeStream([({"content": _idea_content()}, "stop")]),
        FakeStream([({"content": _finalize_content()}, "stop")]),
    ])
    progress_repo = TaskProgressRepository(engine)
    subagent = SubAgentService(
        msg_svc, task_repo, art_repo,
        progress_repo, content_repo,
        tool_dispatcher,
        stub_chat_model_provider(sub_client), agent_loop,
        types.SimpleNamespace(generate=lambda agent_type, invoke: ""),
        skill_loader,
        stub_memory_service(),
        lease=LeaseGuard(task_repo, art_repo, content_repo, progress_repo),
    )

    scheduler = TaskScheduler(
        task_repo, subagent.run, session_svc,
        content_repo, TaskProgressRepository(engine),
        interval=0.01, zombie_timeout=999,
        log_dir=Path(tempfile.mkdtemp()) / "logs",
    )
    return supervisor, subagent, task_service, scheduler, task_repo, session_svc, engine, intent_state


def test_end_to_end_pipeline():
    """4 链路全跑通：supervisor 建图 → idea awaiting_confirm → confirm finished → scheduler 派发 finalize。"""
    sup, sub, task_service, scheduler, task_repo, session_svc, engine, intent_state = _build_assembly()
    session = session_svc.create("集成测试")
    sid = session.id
    intent_state.patch_status(sid, "confirmed")

    # —— 链路 1：supervisor 建图 ——
    events = list(sup.stream(sid, "帮我写一篇夏日博文"))
    assert any(e.type == "done" for e in events), \
        f"缺 done，事件序列: {[e.type for e in events]}"
    assert "task_plan_created" not in [e.type for e in events]
    assert task_repo.count_by_session_statuses(sid, ACTIVE_STATUSES) == 2

    tasks = task_repo.find_by_session_statuses(sid, ACTIVE_STATUSES)
    idea = next(t for t in tasks if t.agent_type == "idea")
    finalize = next(t for t in tasks if t.agent_type == "finalize")
    assert idea.id in finalize.dependencies  # finalize 依赖 idea

    # —— 链路 2：subagent 跑 idea → awaiting_confirm ——
    # 手动占槽 pending→running（不走 scheduler，保持链路 2/4 的时序可控）
    assert task_repo.claim(idea.id, time.time())
    sub.run(idea.id)
    assert task_repo.get(idea.id).status == TaskStatus.AWAITING_CONFIRM

    # 确认前：汇总仍被依赖阻塞（选题待复核≠已完成）
    assert not finalize.can_schedule([task_repo.get(idea.id)])

    # —— 链路 3：confirm idea → finished ——
    task_service.confirm(idea.id, selected=0)
    assert task_repo.get(idea.id).status == TaskStatus.FINISHED

    # —— 链路 4：scheduler 派发 finalize（dep 已解除）——
    assert finalize.can_schedule([task_repo.get(idea.id)])  # 现在可调度
    scheduler._tick()  # 占槽并起 worker 线程跑汇总子 agent

    # 汇总由 worker 线程异步跑，轮询等其离开 pending/running。
    deadline = time.time() + 2.0
    fin = task_repo.get(finalize.id)
    while fin.status in (TaskStatus.PENDING, TaskStatus.RUNNING) and time.time() < deadline:
        time.sleep(0.02)
        fin = task_repo.get(finalize.id)
    # 成品终审门：汇总先达待复核，确认后才 finished
    assert fin.status == TaskStatus.AWAITING_CONFIRM, f"finalize 链路未达待复核，实际: {fin.status}"
    task_service.confirm(finalize.id, None)
    assert task_repo.get(finalize.id).status == TaskStatus.FINISHED


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
