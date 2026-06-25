# kitty/tests/test_tools_create_plan.py
"""CreatePlanTool.run 纯校验契约：成功→Terminal(PlanRequest)、参数错/校验错→Reply(correction)。
运行：.venv/bin/python -m kitty.tests.test_tools_create_plan
"""
from __future__ import annotations

from chorus.domain.task import CreationIntent
from chorus.tools.builtin.create_plan import CreatePlanTool, PlanRequest
from chorus.tools.framework import Reply, Terminal
from chorus.tools import ToolContext


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


def _ctx():
    return ToolContext(skill_loader=None, session_id="s1")


def test_success_returns_terminal_plan_request():
    tool = CreatePlanTool()
    outcome = tool.run(_args(), _ctx())
    assert isinstance(outcome, Terminal)
    pr = outcome.payload
    assert isinstance(pr, PlanRequest)
    assert isinstance(pr.intent, CreationIntent)
    assert pr.intent.topic == "夏日晚风"
    assert pr.intent.image_count == 2
    assert len(pr.steps) == 2
    assert pr.steps[0].agent_type == "idea"
    # summary 是 tool_result.content 语义摘要（落库用）
    assert isinstance(outcome.summary, str) and outcome.summary


def test_missing_intent_key_returns_reply():
    tool = CreatePlanTool()
    outcome = tool.run({"thought": "x", "friendly_reply": "y", "steps": []}, _ctx())
    assert isinstance(outcome, Reply)
    assert "create_plan" in outcome.content or "参数" in outcome.content


def test_bad_step_returns_reply_with_correction():
    """末步非 finalize → validate_steps 抛 ValidationError → Reply(correction)。"""
    tool = CreatePlanTool()
    bad = _args(steps=[{"agent_type": "idea", "deps": [], "focus": "选题"}])  # 末步非 finalize
    outcome = tool.run(bad, _ctx())
    assert isinstance(outcome, Reply)
    assert "finalize" in outcome.content


def test_circular_deps_returns_reply():
    tool = CreatePlanTool()
    # 不能构造真环（deps 只能引前置），构造前向依赖错
    bad = _args(steps=[
        {"agent_type": "idea", "deps": [1], "focus": "x"},  # deps 引后续索引非法
        {"agent_type": "finalize", "deps": [0], "focus": "y"},
    ])
    outcome = tool.run(bad, _ctx())
    assert isinstance(outcome, Reply)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
