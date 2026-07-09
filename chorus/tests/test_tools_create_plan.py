"""CreatePlanTool.run 契约：成功→Terminal + 整图落库；参数错/校验错/落库失败→Reply(correction)。

建图副作用已收进工具，成功 outcome 为 Terminal，副作用验 tasks 表落库。
"""
from __future__ import annotations

from chorus.domain.task import ACTIVE_STATUSES
from chorus.repo.task import TaskRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.session import SessionRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.session import SessionService
from chorus.tests._helpers import fresh_conn, seed_session
from chorus.tools.builtin.create_plan import CreatePlanTool
from chorus.tools.framework import Reply, Terminal, ToolContext


def _args(topic="夏日晚风", steps=None, intent_extras=None):
    if steps is None:
        steps = [
            {"agent_type": "idea", "deps": [], "focus": "选题"},
            {"agent_type": "finalize", "deps": [0], "focus": "汇总"},
        ]
    intent = {"topic": topic, "style": "轻松", "image_count": 2}
    if intent_extras:
        intent.update(intent_extras)
    return {"thought": "x", "friendly_reply": "好的", "intent": intent, "steps": steps}


def _build():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = TaskRepository(conn)
    content_repo = TaskContentRepository(conn)
    tool = CreatePlanTool(repo, content_repo)
    ctx = ToolContext(session_id="s1")
    return conn, repo, content_repo, tool, ctx


def test_success_returns_terminal_and_persists_tasks():
    conn, repo, content_repo, tool, ctx = _build()
    outcome = tool.run(_args(), ctx)
    assert isinstance(outcome, Terminal)
    assert isinstance(outcome.content, str) and outcome.content  # 如实建图摘要
    assert "pipeline=" in outcome.content  # 携真实流水线标识，非写死话术
    # 整图落库：两个活跃任务，会话标识回填
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 2
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    assert {t.agent_type for t in tasks} == {"idea", "finalize"}
    assert all(t.session_id == "s1" for t in tasks)
    assert all(t.created_at > 0 for t in tasks)  # 时间戳已落库
    # 内容行同落：每条任务对应一条内容
    contents = content_repo.load_many([t.id for t in tasks])
    assert set(contents.keys()) == {t.id for t in tasks}
    idea_id = next(t.id for t in tasks if t.agent_type == "idea")
    assert "夏日晚风" in contents[idea_id].invoke_message


def test_unconfirmed_intent_blocks_plan_creation():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    repo = TaskRepository(conn)
    content_repo = TaskContentRepository(conn)
    intent = IntentStateService(IntentStateRepository(conn), SessionService(SessionRepository(conn)))
    tool = CreatePlanTool(repo, content_repo, intent)
    outcome = tool.run(_args(), ToolContext(session_id="s1"))
    assert isinstance(outcome, Reply)
    assert "blocked" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0


def test_missing_intent_key_returns_reply():
    _, _, _, tool, ctx = _build()
    outcome = tool.run({"thought": "x", "friendly_reply": "y", "steps": []}, ctx)
    assert isinstance(outcome, Reply)
    assert "create_plan" in outcome.content or "参数" in outcome.content


def test_bad_step_returns_reply_with_correction():
    """末步非 finalize → validate_steps 抛 ValidationError → Reply(correction)，不落库。"""
    _, repo, _, tool, ctx = _build()
    bad = _args(steps=[{"agent_type": "idea", "deps": [], "focus": "选题"}])  # 末步非 finalize
    outcome = tool.run(bad, ctx)
    assert isinstance(outcome, Reply)
    assert "finalize" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0  # 校验失败不落库


def test_circular_deps_returns_reply():
    _, repo, _, tool, ctx = _build()
    # 不能构造真环，构造前向依赖错
    bad = _args(steps=[
        {"agent_type": "idea", "deps": [1], "focus": "x"},  # 依赖后续索引非法
        {"agent_type": "finalize", "deps": [0], "focus": "y"},
    ])
    outcome = tool.run(bad, ctx)
    assert isinstance(outcome, Reply)
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
