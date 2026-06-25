# kitty/tests/test_agent_runtime.py
"""AgentContext / TurnState 运行时状态断言。

覆盖 ``kitty/agents/runtime.py``：多智能体字段（source/task_id）默认值、
``TurnState.reset`` 保留回合级固定字段（source 不被清）、iteration 计数。
loop 运行时状态机契约的锚点。

运行：``.venv/bin/python -m kitty.tests.test_agent_runtime``
"""
from __future__ import annotations

from chorus.agents import AgentContext


def test_agent_context_multiagent_fields():
    ctx = AgentContext(session_id="s", source="subagent", task_id="t1")
    assert ctx.source == "subagent"
    assert ctx.task_id == "t1"
    # 默认 supervisor
    ctx2 = AgentContext(session_id="s")
    assert ctx2.source == "supervisor"
    assert ctx2.task_id is None
    # reset 不清 source（回合级固定）
    ctx.turn.reset(3)
    assert ctx.turn.iteration_index == 3
    assert ctx.source == "subagent"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
