# kitty/tests/test_tools_create_plan.py
"""CreatePlanTool.run 契约：成功→Terminal + 整图落库；参数错/校验错/落库失败→Reply(correction)。

建图副作用（expand + 事务 insert）已收进工具，成功 outcome 为 Terminal(content=如实建图摘要)，
side effect 验 tasks 表落库。运行：.venv/bin/python -m kitty.tests.test_tools_create_plan
"""
from __future__ import annotations

from chorus.domain.task import ACTIVE_STATUSES
from chorus.repositories.task import TaskRepository
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
    tool = CreatePlanTool(repo, conn, clock=lambda: 1.0)
    ctx = ToolContext(session_id="s1")
    return conn, repo, tool, ctx


def test_success_returns_terminal_and_persists_tasks():
    conn, repo, tool, ctx = _build()
    outcome = tool.run(_args(), ctx)
    assert isinstance(outcome, Terminal)
    assert isinstance(outcome.content, str) and outcome.content  # 如实建图摘要
    assert "pipeline=" in outcome.content  # 携真实 pipeline_id，非写死话术
    # 整图落库：idea + finalize 两个 active task，session_id 回填
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 2
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    assert {t.agent_type for t in tasks} == {"idea", "finalize"}
    assert all(t.session_id == "s1" for t in tasks)
    assert all(t.created_at == 1.0 for t in tasks)  # clock 注入生效


def test_missing_intent_key_returns_reply():
    _, _, tool, ctx = _build()
    outcome = tool.run({"thought": "x", "friendly_reply": "y", "steps": []}, ctx)
    assert isinstance(outcome, Reply)
    assert "create_plan" in outcome.content or "参数" in outcome.content


def test_bad_step_returns_reply_with_correction():
    """末步非 finalize → validate_steps 抛 ValidationError → Reply(correction)，不落库。"""
    _, repo, tool, ctx = _build()
    bad = _args(steps=[{"agent_type": "idea", "deps": [], "focus": "选题"}])  # 末步非 finalize
    outcome = tool.run(bad, ctx)
    assert isinstance(outcome, Reply)
    assert "finalize" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0  # 校验失败不落库


def test_circular_deps_returns_reply():
    _, repo, tool, ctx = _build()
    # 不能构造真环（deps 只能引前置），构造前向依赖错
    bad = _args(steps=[
        {"agent_type": "idea", "deps": [1], "focus": "x"},  # deps 引后续索引非法
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
