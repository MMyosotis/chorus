"""AgentContext / TurnState 运行时状态断言。

覆盖多智能体字段默认值与回合级固定字段不被 reset 清空。
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
    ctx.turn.reset()
    assert ctx.source == "subagent"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
