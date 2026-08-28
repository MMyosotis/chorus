"""AgentContext / TurnState 运行时状态断言。

覆盖多智能体字段默认值与回合级固定字段不被 reset 清空。
"""
from __future__ import annotations

from chorus.agents import AgentContext
from chorus.agents.runtime import ModelCallRecorder
from chorus.domain.trace import ModelUsage


def test_agent_context_multiagent_fields():
    ctx = AgentContext(session_id="s", chat_model="test-model", source="subagent", task_id="t1")
    assert ctx.source == "subagent"
    assert ctx.task_id == "t1"
    # 默认 supervisor
    ctx2 = AgentContext(session_id="s", chat_model="test-model")
    assert ctx2.source == "supervisor"
    assert ctx2.task_id is None
    # reset 不清 source（回合级固定）
    ctx.turn.reset()
    assert ctx.source == "subagent"


def test_model_call_recorder_collects_stats():
    recorder = ModelCallRecorder()
    usage = ModelUsage(input_tokens=10, output_tokens=20, total_tokens=30)
    stats = recorder.success(usage)
    assert stats.status == "success"
    assert stats.usage is usage
    assert stats.duration_ms >= 0

    recorder = ModelCallRecorder()
    stats = recorder.failure(ValueError("boom"))
    assert stats.status == "error"
    assert stats.error == "boom"
    assert stats.usage is None
    assert stats.duration_ms >= 0


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
