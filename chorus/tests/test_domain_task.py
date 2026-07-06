"""任务图领域纯函数表驱动断言：PostCard 契约 / 状态机 / AgentProfile / pipeline。

覆盖 state + profiles + post + pipeline 的纯逻辑，不碰 DB。
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
    TaskContent,
    TaskStatus,
    CreationIntent,
    StepSpec,
    ValidationError,
    is_legal_transition,
    parse_sections,
    select_display_pipeline,
    topological_order,
    validate_steps,
)


def _mk(status, deps=None, **kw):
    base = dict(
        id="t", session_id="s", pipeline_id="p", agent_type="idea",
        status=status, dependencies=deps or [],
        created_at=0.0, updated_at=0.0,
    )
    base.update(kw)
    return Task(**base)


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


def test_legal_transitions_table():
    # 终态不可再转移
    assert not any(f == TaskStatus.FINISHED for f, _ in LEGAL_TRANSITIONS)
    # 关键转移都在
    assert is_legal_transition("pending", "running")
    assert is_legal_transition("running", "awaiting_confirm")
    assert is_legal_transition("awaiting_confirm", "finished")
    assert is_legal_transition("awaiting_confirm", "pending")  # retry
    assert is_legal_transition("failed", "pending")  # retry 复活
    # 批量取消须支持运行中转取消
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
    assert _mk("pending").can_schedule([dep_finished]) is True
    # 上游失败则后继阻塞
    assert _mk("pending").can_schedule([dep_failed]) is False
    # 非 pending 不可调度
    assert _mk("running").can_schedule([dep_finished]) is False
    assert _mk("awaiting_confirm").can_schedule([dep_finished]) is False
    # 无依赖的可调度
    assert _mk("pending").can_schedule([]) is True


def test_status_sets():
    assert ACTIVE_STATUSES == frozenset({"pending", "running", "awaiting_confirm"})
    assert TERMINAL_STATUSES == frozenset({"finished", "failed", "cancelled"})
    assert CANCELLABLE_STATUSES == ACTIVE_STATUSES  # cancel 可翻转全部非终态
    assert ACTIVE_STATUSES.isdisjoint(TERMINAL_STATUSES)


def test_select_display_pipeline():
    active = [_mk("running", id="a")]
    finished = [_mk("finished", id="f1"), _mk("cancelled", id="c1")]
    assert select_display_pipeline(active, finished) == active  # active 优先
    # 无运行中则返已完成（不含已取消）
    assert select_display_pipeline([], finished) == [_mk("finished", id="f1")]
    assert select_display_pipeline([], []) == []


def test_agent_profiles_registry():
    assert set(AGENT_PROFILES.keys()) == {"idea", "script", "image", "finalize"}
    assert "generate_image" in TOOL_WHITELISTS["image"]  # 唯一带生图的角色
    # 前三步不含生图
    for at in ("idea", "script", "finalize"):
        assert "generate_image" not in TOOL_WHITELISTS[at]
    # 入场台词纯文本无 emoji
    for p in AGENT_PROFILES.values():
        assert p.enter_line and p.display_name
        assert p.expected_sections == ("artifacts", "narrative")


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
    # 非首步无依赖
    with pytest.raises(ValidationError):
        validate_steps([
            StepSpec("idea", [], "x"),
            StepSpec("script", [], "y"),
            StepSpec("finalize", [1], "z"),
        ])


def test_expand_pipeline():
    intent = CreationIntent(topic="夏日晚风", style="轻松", image_count=2)
    steps = [
        StepSpec("idea", [], "选题"),
        StepSpec("finalize", [0], "汇总"),
    ]
    pairs = intent.expand_to_tasks(steps, "sess-x", 1000.0)
    assert len(pairs) == 2
    tasks = [t for t, _ in pairs]
    contents = [c for _, c in pairs]
    assert all(t.status == TaskStatus.PENDING for t in tasks)
    assert all(t.session_id == "sess-x" and t.created_at == 1000.0 for t in tasks)
    assert tasks[0].dependencies == []
    assert tasks[1].dependencies == [tasks[0].id]
    assert all(t.pipeline_id == tasks[0].pipeline_id for t in tasks)
    assert "夏日晚风" in contents[0].invoke_message
    # 内容行对齐调度行标识
    assert all(c.task_id == t.id for t, c in pairs)


def test_expand_pipeline_image_progress_total():
    """image 步骤的 progress_total 落进 TaskContent，调度行不携带。"""
    intent = CreationIntent(topic="t", image_count=4)
    steps = [StepSpec("image", [], "配图"), StepSpec("finalize", [0], "汇总")]
    pairs = intent.expand_to_tasks(steps, "s", 0.0)
    image_task, image_content = next(p for p in pairs if p[0].agent_type == "image")
    assert image_content.progress_total == 4


def test_render_invoke_message_injects_deps_and_feedback():
    content = TaskContent(
        task_id="t", invoke_message="骨架",
        feedback={"note": "改标题"},
    )
    out = content.render_invoke({"d1": {"title": "x"}}, {"prev": 1})
    assert "骨架" in out
    assert "前置步骤产物" in out
    assert "你上一轮的产物" in out
    assert "用户反馈" in out
    # 无注入时只骨架
    bare = TaskContent(task_id="t", invoke_message="骨架")
    assert bare.render_invoke({}, None) == "骨架"


def test_parse_sections():
    content = "引导语\n<<<ARTIFACTS:json>>>\n{\"a\":1}\n<<<ARTIFACTS_END>>>\n中间\n<<<NARRATIVE:json>>>\n{\"b\":2}\n<<<NARRATIVE_END>>>"
    secs = parse_sections(content)
    assert secs["artifacts"].strip() == '{"a":1}'
    assert secs["narrative"].strip() == '{"b":2}'


def test_parse_output_idea_ok():
    content = (
        '<<<ARTIFACTS:json>>>\n{"candidates":[{"index":0,"title":"t","angle":"a","reason":"r"}],"selected":null}\n<<<ARTIFACTS_END>>>\n'
        '<<<NARRATIVE:json>>>\n{"awaiting_line":"y","done_line":"z"}\n<<<NARRATIVE_END>>>'
    )
    artifacts, narrative = AGENT_PROFILES["idea"].parse_output(content)
    assert len(artifacts.candidates) == 1
    assert artifacts.candidates[0].title == "t"
    assert narrative.done_line == "z"
    assert narrative.awaiting_line == "y"


def test_parse_output_narrative_bad_type():
    """narrative 字段类型错（done_line 非 str）→ ValidationError。"""
    content = (
        '<<<ARTIFACTS:json>>>\n{"candidates":[]}\n<<<ARTIFACTS_END>>>\n'
        '<<<NARRATIVE:json>>>\n{"awaiting_line":"y","done_line":123}\n<<<NARRATIVE_END>>>'
    )
    with pytest.raises(ValidationError):
        AGENT_PROFILES["idea"].parse_output(content)


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
        f'<<<NARRATIVE:json>>>\n{{"awaiting_line":"","done_line":""}}\n<<<NARRATIVE_END>>>'
    )
    artifacts, _ = AGENT_PROFILES["finalize"].parse_output(content)
    assert artifacts.title == "夏日晚风"


def test_parse_output_missing_section():
    with pytest.raises(ValidationError):
        AGENT_PROFILES["idea"].parse_output("<<<ARTIFACTS:json>>>\n{}\n<<<ARTIFACTS_END>>>")  # 缺 NARRATIVE


def _task(tid, deps=None, created_at=0.0):
    return Task(
        id=tid, session_id="s", pipeline_id="p", agent_type="idea",
        status="pending", dependencies=deps or [],
        created_at=created_at, updated_at=0.0,
    )


def test_topological_order_linear_chain():
    """线性链：a→b→c 拓扑序即 a, b, c。"""
    a, b, c = _task("a"), _task("b", ["a"]), _task("c", ["b"])
    assert [t.id for t in topological_order([c, b, a])] == ["a", "b", "c"]


def test_topological_order_parallel_branches():
    """并行分支：a→{b,c}→d，b/c 同层，d 在最后。"""
    a = _task("a")
    b = _task("b", ["a"], created_at=1.0)
    c = _task("c", ["a"], created_at=2.0)
    d = _task("d", ["b", "c"])
    out = [t.id for t in topological_order([d, c, b, a])]
    assert out[0] == "a"
    assert out[-1] == "d"
    assert set(out[1:3]) == {"b", "c"}


def test_topological_order_same_layer_tiebreak():
    """同层按创建时间升序再以标识兜底，稳定。"""
    a = _task("a")
    b = _task("b", ["a"], created_at=5.0)
    c = _task("c", ["a"], created_at=2.0)
    assert [t.id for t in topological_order([a, b, c])] == ["a", "c", "b"]


def test_topological_order_ignores_external_dep():
    """依赖标识不在列表内（跨流水线）忽略，不阻塞排序。"""
    a = _task("a", ["外部id"])
    assert [t.id for t in topological_order([a])] == ["a"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
