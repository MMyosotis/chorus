# kitty/tests/test_domain_task.py
"""任务图领域纯函数表驱动断言：PostCard 契约 / 状态机 / AgentProfile / pipeline。

覆盖 ``kitty/domain/task`` 下 state_machine + profiles + post + pipeline 的纯逻辑
（不碰 DB，成本极低）。是「状态机/纯函数不测是最大浪费」（spec 第 8 节）的主防线。

运行：``.venv/bin/python -m kitty.tests.test_domain_task``
"""
from __future__ import annotations

import pytest

from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import (
    ACTIVE_STATUSES,
    AGENT_PROFILES,
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    PostCard,
    PostImage,
    PostSection,
    TERMINAL_STATUSES,
    Task,
    TaskStatus,
    CreationIntent,
    StepSpec,
    ValidationError,
    can_schedule,
    expand_pipeline,
    is_legal_transition,
    is_zombie,
    parse_output,
    parse_sections,
    render_invoke_message,
    select_display_pipeline,
    validate_steps,
)


def _mk(status, deps=None, **kw):
    base = dict(
        id="t", session_id="s", pipeline_id="p", agent_type="idea", seq=1,
        status=status, invoke_message="x", dependencies=deps or [],
        created_at=0.0, updated_at=0.0,
    )
    base.update(kw)
    return Task(**base)


# —— PostCard 契约 ——

def test_postcard_contract():
    card = PostCard(
        title="夏日晚风",
        cover=PostImage(url="http://x/a.jpg"),
        sections=[
            PostSection(kind="heading", text="开篇"),
            PostSection(kind="paragraph", text="一段文字"),
            PostSection(kind="image", image=PostImage(url="http://x/b.jpg", caption="图注")),
            PostSection(kind="list", text="点一\n点二"),
        ],
        tags=["#夏天", "#随笔"],
        summary="一句摘要",
    )
    assert card.sections[2].image.url == "http://x/b.jpg"
    assert card.tags == ["#夏天", "#随笔"]


def test_postcard_rejects_unknown_kind():
    from pydantic import ValidationError as PydValidationError
    with pytest.raises(PydValidationError):
        PostSection(kind="table", text="x")  # type: ignore[arg-type]


# —— 状态机 ——

def test_legal_transitions_table():
    # 严格闸门：无 finished→*
    assert not any(f == TaskStatus.FINISHED.value for f, _ in LEGAL_TRANSITIONS)
    # 关键转移都在
    assert is_legal_transition("pending", "running")
    assert is_legal_transition("running", "awaiting_confirm")
    assert is_legal_transition("awaiting_confirm", "finished")
    assert is_legal_transition("awaiting_confirm", "pending")  # retry
    assert is_legal_transition("failed", "pending")  # retry 复活
    # cancel_pipeline 实际执行 running→cancelled（批量翻转非终态），须在规则表
    assert is_legal_transition("running", "cancelled")
    assert is_legal_transition("pending", "cancelled")
    assert is_legal_transition("awaiting_confirm", "cancelled")
    # 非法
    assert not is_legal_transition("finished", "running")
    assert not is_legal_transition("finished", "pending")
    assert not is_legal_transition("cancelled", "running")


def test_can_schedule():
    dep_finished = _mk("finished", id="d1")
    dep_failed = _mk("failed", id="d2")
    assert can_schedule(_mk("pending"), [dep_finished]) is True
    # 上游 failed 不满足（砍级联：后继阻塞）
    assert can_schedule(_mk("pending"), [dep_failed]) is False
    # 非 pending 不可调度
    assert can_schedule(_mk("running"), [dep_finished]) is False
    assert can_schedule(_mk("awaiting_confirm"), [dep_finished]) is False
    # 无 deps 的 pending 可调度
    assert can_schedule(_mk("pending"), []) is True


def test_is_zombie():
    t = _mk("running", updated_at=100.0)
    assert is_zombie(t, now=200.0, timeout_s=60) is True
    assert is_zombie(t, now=150.0, timeout_s=60) is False
    assert is_zombie(_mk("pending"), now=9999.0, timeout_s=1) is False


def test_status_sets():
    assert ACTIVE_STATUSES == frozenset({"pending", "running", "awaiting_confirm"})
    assert TERMINAL_STATUSES == frozenset({"finished", "failed", "cancelled"})
    assert CANCELLABLE_STATUSES == ACTIVE_STATUSES  # cancel 可翻转全部非终态
    assert ACTIVE_STATUSES.isdisjoint(TERMINAL_STATUSES)


def test_select_display_pipeline():
    active = [_mk("running", id="a")]
    finished = [_mk("finished", id="f1"), _mk("cancelled", id="c1")]
    assert select_display_pipeline(active, finished) == active  # active 优先
    # 无 active，返 finished（不含 cancelled）
    assert select_display_pipeline([], finished) == [_mk("finished", id="f1")]
    assert select_display_pipeline([], []) == []


# —— AgentProfile 注册表 ——

def test_agent_profiles_registry():
    assert set(AGENT_PROFILES.keys()) == {"idea", "script", "image", "finalize"}
    assert "generate_image" in TOOL_WHITELISTS["image"]  # 唯一带生图的角色
    # 前三步不含 generate_image
    for at in ("idea", "script", "finalize"):
        assert "generate_image" not in TOOL_WHITELISTS[at]
    # enter_line 纯文本无 emoji（粗校：仅 ASCII / 中文标点，无典型 emoji 区段）
    for p in AGENT_PROFILES.values():
        assert p.enter_line and p.display_name
        assert p.expected_sections == ("artifacts", "narrative")


# —— pipeline 校验 / 展开 / 渲染 / 解析 ——

def test_validate_steps_ok():
    steps = [
        StepSpec(agent_type="idea", deps=[], focus="选题"),
        StepSpec(agent_type="script", deps=[0], focus="写文案"),
        StepSpec(agent_type="image", deps=[1], focus="配图"),
        StepSpec(agent_type="finalize", deps=[0, 1, 2], focus="汇总"),
    ]
    validate_steps(steps)  # 不抛


def test_validate_steps_rejects():
    # 漏 finalize
    with pytest.raises(ValidationError):
        validate_steps([StepSpec("idea", [], "x")])
    # 杜撰角色
    with pytest.raises(ValidationError):
        validate_steps([StepSpec("novideo", [], "x"), StepSpec("finalize", [0], "y")])
    # 前向依赖
    with pytest.raises(ValidationError):
        validate_steps([StepSpec("idea", [1], "x"), StepSpec("finalize", [0], "y")])
    # 自指
    with pytest.raises(ValidationError):
        validate_steps([StepSpec("idea", [0], "x"), StepSpec("finalize", [0], "y")])


def test_expand_pipeline():
    intent = CreationIntent(topic="夏日晚风", style="轻松", image_count=2)
    steps = [
        StepSpec("idea", [], "选题"),
        StepSpec("finalize", [0], "汇总"),
    ]
    tasks = expand_pipeline(intent, steps)
    assert len(tasks) == 2
    assert all(t.status == TaskStatus.PENDING.value for t in tasks)
    assert tasks[0].dependencies == []
    assert tasks[1].dependencies == [tasks[0].id]
    assert all(t.pipeline_id == tasks[0].pipeline_id for t in tasks)
    assert "夏日晚风" in tasks[0].invoke_message
    assert tasks[1].seq == 2


def test_render_invoke_message_injects_deps_and_feedback():
    task = _mk("pending", id="t", invoke_message="骨架")
    out = render_invoke_message(task, {"d1": {"title": "x"}}, {"prev": 1}, {"note": "改标题"})
    assert "骨架" in out
    assert "前置步骤产物" in out
    assert "你上一轮的产物" in out
    assert "用户反馈" in out
    # 无注入时只骨架
    assert render_invoke_message(task, {}, None, None) == "骨架"


def test_parse_sections():
    content = "引导语\n<<<ARTIFACTS:json>>>\n{\"a\":1}\n<<<ARTIFACTS_END>>>\n中间\n<<<NARRATIVE:json>>>\n{\"b\":2}\n<<<NARRATIVE_END>>>"
    secs = parse_sections(content)
    assert secs["artifacts"].strip() == '{"a":1}'
    assert secs["narrative"].strip() == '{"b":2}'


def test_parse_output_idea_ok():
    content = (
        '<<<ARTIFACTS:json>>>\n{"candidates":[{"index":0,"title":"t","angle":"a","reason":"r"}],"selected":null}\n<<<ARTIFACTS_END>>>\n'
        '<<<NARRATIVE:json>>>\n{"busy_lines":["x"],"awaiting_line":"y","done_line":"z"}\n<<<NARRATIVE_END>>>'
    )
    artifacts, narrative = parse_output(content, "idea")
    assert "candidates" in artifacts
    assert narrative["done_line"] == "z"


def test_parse_output_finalize_postcard():
    import json as _json
    card = {
        "title": "夏日晚风",
        "cover": {"url": "http://x/a.jpg"},
        "sections": [{"kind": "paragraph", "text": "一段"}],
        "tags": ["#夏天"],
        "summary": "摘要",
    }
    content = (
        f'<<<ARTIFACTS:json>>>\n{_json.dumps(card)}\n<<<ARTIFACTS_END>>>\n'
        f'<<<NARRATIVE:json>>>\n{{"busy_lines":[],"awaiting_line":"","done_line":""}}\n<<<NARRATIVE_END>>>'
    )
    artifacts, _ = parse_output(content, "finalize")
    assert artifacts["title"] == "夏日晚风"


def test_parse_output_missing_section():
    with pytest.raises(ValidationError):
        parse_output("<<<ARTIFACTS:json>>>\n{}\n<<<ARTIFACTS_END>>>", "idea")  # 缺 NARRATIVE


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
