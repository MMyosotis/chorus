"""任务图领域纯函数表驱动断言：PostCard 契约 / 状态机 / AgentProfile / pipeline。

覆盖 state + profiles + post + pipeline 的纯逻辑，不碰 DB。
"""
from __future__ import annotations

import pytest

from chorus.config import TOOL_WHITELISTS
from chorus.domain.intent import Intent
from chorus.domain.task import (
    ACTIVE_STATUSES,
    AGENT_PROFILES,
    CANCELLED_PIPELINE_RECEIPT,
    CANCELLABLE_STATUSES,
    DeliveredProduct,
    LEGAL_TRANSITIONS,
    PostCard,
    TERMINAL_STATUSES,
    Task,
    TaskPlan,
    TaskProgress,
    TaskStatus,
    StepSpec,
    ValidationError,
    build_task_graph,
    dump_task_graph,
    format_product_list,
    invoke_text,
    is_legal_transition,
    build_delivered_products,
    render_delivery_receipt,
    select_delivered_tasks,
    select_display_pipeline,
    select_pipeline_id,
    topological_order,
    IdeaArtifacts,
    IdeaCandidate,
    ImageArtifacts,
    ImageItem,
    ScriptArtifacts,
)
from chorus.domain.task.errors import AbandonError


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
        markdown="---\ntitle: 夏日晚风\n---\n\n一段文字\n\n![图注](http://x/b.jpg)",
        meta={"preview_ref": "a/b", "stylesheet_ref": "a/c", "title": "夏日晚风"},
    )
    assert card.markdown.startswith("---\ntitle: 夏日晚风")
    assert card.meta["preview_ref"] == "a/b"
    assert card.meta["title"] == "夏日晚风"


def test_delivered_products_filter_and_format():
    draft = _mk(TaskStatus.AWAITING_CONFIRM, id="draft", agent_type="finalize", created_at=4.0)
    later = _mk(TaskStatus.FINISHED, id="later", agent_type="finalize", created_at=2.0)
    first = _mk(
        TaskStatus.FINISHED, id="first", agent_type="finalize", created_at=1.0,
        message_id="m1",
    )
    script = _mk(TaskStatus.FINISHED, id="script", agent_type="script", created_at=3.0)
    tasks = [draft, script, later, first]
    assert [task.id for task in select_delivered_tasks(tasks)] == ["later", "first"]
    pairs = [
        (task, PostCard(markdown=f"{task.id}正文", meta={"title": title}))
        for task, title in [(later, "后发"), (first, "先发")]
    ]
    products = build_delivered_products(pairs)
    assert isinstance(products[0], DeliveredProduct)
    assert [product.id for product in products] == ["first", "later"]
    assert format_product_list(products) == "- first 《先发》\n- later 《后发》"
    assert "暂无已交付成品" in format_product_list([])


def test_legal_transitions_table():
    # 终态不可再转移
    assert not any(f == TaskStatus.FINISHED for f, _ in LEGAL_TRANSITIONS)
    # 关键转移都在
    assert is_legal_transition("pending", "running")
    assert is_legal_transition("running", "awaiting_confirm")
    assert is_legal_transition("awaiting_confirm", "finished")
    assert is_legal_transition("awaiting_confirm", "pending")  # retry
    assert is_legal_transition("failed", "pending")  # retry 复活
    # 批量取消可覆盖运行中与失败：放弃整条流水线要能把任何残余任务了结掉
    assert is_legal_transition("pending", "cancelled")
    assert is_legal_transition("awaiting_confirm", "cancelled")
    assert is_legal_transition("running", "cancelled")
    assert is_legal_transition("failed", "cancelled")
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
    assert CANCELLABLE_STATUSES == frozenset({"pending", "running", "awaiting_confirm", "failed"})
    assert ACTIVE_STATUSES.isdisjoint(TERMINAL_STATUSES)


def test_select_display_pipeline():
    active = [_mk("running", id="a")]
    terminal = [_mk("finished", id="f1"), _mk("failed", id="x1"), _mk("cancelled", id="c1")]
    assert select_display_pipeline(active, terminal) == active  # active 优先
    # 无运行中则返已完成与失败（不含已取消）
    assert select_display_pipeline([], terminal) == [_mk("finished", id="f1"), _mk("failed", id="x1")]
    assert select_display_pipeline([], []) == []


def test_select_pipeline_id_prefers_active_then_latest_terminal():
    active = [_mk("running", id="active", pipeline_id="active-pipeline", updated_at=1.0)]
    terminal = [_mk("finished", id="old", pipeline_id="old-pipeline", updated_at=5.0)]
    assert select_pipeline_id(active, terminal) == "active-pipeline"
    assert select_pipeline_id([], terminal) == "old-pipeline"
    assert select_pipeline_id([], []) is None


def test_agent_profiles_registry():
    assert set(AGENT_PROFILES.keys()) == {"idea", "script", "image", "finalize"}
    assert "generate_image" in TOOL_WHITELISTS["image"]  # 唯一带生图的角色
    # 前三步不含生图
    for at in ("idea", "script", "finalize"):
        assert "generate_image" not in TOOL_WHITELISTS[at]
    # 展示名非空
    for p in AGENT_PROFILES.values():
        assert p.display_name


def test_activity_line_injected_into_graph():
    """角色活动台词经 graph 序列化注入 progress，前端直接取 activity_line。"""
    task = _mk(TaskStatus.RUNNING, agent_type="image")
    prog = TaskProgress(task_id="t", activity_kind="drawing")
    graph = build_task_graph("p", [task], {}, {"t": prog}, {}, True)
    data = dump_task_graph(graph)
    node = data["tasks"][0]
    assert node["progress"]["activity_kind"] == "drawing"
    assert node["progress"]["activity_line"] == "正在生成图片"
    # 角色差异：选题官思考态台词与配图官不同
    idea_task = _mk(TaskStatus.RUNNING, id="idea", agent_type="idea")
    idea_prog = TaskProgress(task_id="idea", activity_kind="thinking")
    idea_graph = build_task_graph("p", [idea_task], {}, {"idea": idea_prog}, {}, True)
    assert dump_task_graph(idea_graph)["tasks"][0]["progress"]["activity_line"] == "正在梳理选题"


def test_validate_steps_ok():
    steps = [
        StepSpec(agent_type="idea", deps=[]),
        StepSpec(agent_type="script", deps=[0]),
        StepSpec(agent_type="image", deps=[1]),
        StepSpec(agent_type="finalize", deps=[0, 1, 2]),
    ]
    TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3), steps=steps)  # 构造即校验，不抛


def test_validate_steps_rejects():
    # 漏 finalize
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3),
                 steps=[StepSpec("idea", [])])
    # 杜撰角色
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3),
                 steps=[StepSpec("novideo", []), StepSpec("finalize", [0])])
    # 前向依赖
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3),
                 steps=[StepSpec("idea", [1]), StepSpec("finalize", [0])])
    # 自指
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3),
                 steps=[StepSpec("idea", [0]), StepSpec("finalize", [0])])
    # 非首步无依赖
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t", image_count=3), steps=[
            StepSpec("idea", []),
            StepSpec("script", []),
            StepSpec("finalize", [1]),
        ])


def test_expand_pipeline():
    intent = Intent(topic="夏日晚风", style="轻松", image_count=2)
    steps = [
        StepSpec("idea", []),
        StepSpec("finalize", [0]),
    ]
    pairs = TaskPlan(
        session_id="sess-x", intent=intent, steps=steps, created_at=1000.0,
    ).expand()
    assert len(pairs) == 2
    tasks = [task for task, _ in pairs]
    paired_steps = [step for _, step in pairs]
    assert all(task.status == TaskStatus.PENDING for task in tasks)
    assert all(task.session_id == "sess-x" and task.created_at == 1000.0 for task in tasks)
    assert tasks[0].dependencies == []
    assert tasks[1].dependencies == [tasks[0].id]
    assert all(task.pipeline_id == tasks[0].pipeline_id for task in tasks)
    assert [step.agent_type for step in paired_steps] == ["idea", "finalize"]
    assert paired_steps[1].deps == [0]


def test_invoke_text_markdown_bodies_return_raw():
    # markdown 本体给原文，不带 JSON 壳与转义
    script = ScriptArtifacts(markdown="第一行\n第二行")
    assert invoke_text(script) == "第一行\n第二行"
    card = PostCard(markdown="# 标题\n正文", meta={"title": "标题"})
    assert invoke_text(card) == "# 标题\n正文"


def test_invoke_text_structured_bodies_return_full_json():
    # 结构化产物给全量 JSON：选题保留全部候选与 selected，不裁剪
    idea = IdeaArtifacts(candidates=[
        IdeaCandidate(index=0, title="甲", angle="a", reason="r"),
        IdeaCandidate(index=1, title="乙", angle="b", reason="r"),
    ], selected=1)
    idea_text = invoke_text(idea)
    assert '"甲"' in idea_text and '"乙"' in idea_text
    assert '"selected": 1' in idea_text
    image = ImageArtifacts(images=[ImageItem(url="http://x/a.png", caption="图注")])
    image_text = invoke_text(image)
    assert "http://x/a.png" in image_text and "图注" in image_text


def test_parse_output_idea_ok():
    content = "### 阳台慢时光\n- 视角：物候\n- 理由：光线挪动"
    artifacts = AGENT_PROFILES["idea"].parse_output(content)
    assert len(artifacts.candidates) == 1
    assert artifacts.candidates[0].title == "阳台慢时光"


def test_parse_output_finalize_postcard():
    content = ("---\n"
               "title: 夏日晚风\n"
               "preview_ref: web-blog/preview/desktop.html\n"
               "stylesheet_ref: web-blog/preview/desktop.css\n"
               "summary: 摘要\ntags: [夏天]\n"
               "---\n\n一段正文")
    artifacts = AGENT_PROFILES["finalize"].parse_output(content)
    assert artifacts.meta["title"] == "夏日晚风"
    assert artifacts.meta["preview_ref"] == "web-blog/preview/desktop.html"


def test_parse_output_abandon_block_raises():
    """任一角色产物为 # 失败 块时抛 AbandonError，携带失败说明。"""
    body = "# 失败\n配图服务持续返回 Error，换写法仍无效"
    for agent_type in ("idea", "script", "image", "finalize"):
        with pytest.raises(AbandonError) as exc:
            AGENT_PROFILES[agent_type].parse_output(body)
        assert exc.value.reason == "配图服务持续返回 Error，换写法仍无效"


def test_parse_output_abandon_same_line_reason():
    """# 失败：说明 同行写法也命中失败块，标题含「失败」前缀不误判。"""
    with pytest.raises(AbandonError) as exc:
        AGENT_PROFILES["script"].parse_output("# 失败：工具持续返回 Error")
    assert exc.value.reason == "工具持续返回 Error"
    artifacts = AGENT_PROFILES["script"].parse_output("---\ntitle: 失败者的逆袭\n---\n\n正文。")
    assert artifacts.markdown.startswith("---\ntitle: 失败者的逆袭")


def test_parse_output_normal_not_misread_as_abandon():
    """三级标题含「失败」二字不误判为失败块（失败块须一级标题）。"""
    content = "### 失败者的逆袭\n- 视角：反转\n- 理由：情绪钩子"
    artifacts = AGENT_PROFILES["idea"].parse_output(content)
    assert artifacts.candidates[0].title == "失败者的逆袭"


def _task(tid, deps=None, created_at=0.0):
    return Task(
        id=tid, session_id="s", pipeline_id="p", agent_type="idea",
        status="pending", dependencies=deps or [],
        created_at=created_at, updated_at=0.0,
    )


def test_topological_order_linear_chain():
    """线性链：a->b->c 拓扑序即 a, b, c。"""
    a, b, c = _task("a"), _task("b", ["a"]), _task("c", ["b"])
    assert [t.id for t in topological_order([c, b, a])] == ["a", "b", "c"]


def test_topological_order_parallel_branches():
    """并行分支：a->{b,c}->d，b/c 同层，d 在最后。"""
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


def test_delivery_receipt_texts():
    """收口回执：成品直给标识与全文，取消只给一句话。"""
    card = PostCard(markdown="正文全文", meta={"title": "夏日晚风"})
    assert render_delivery_receipt("t-final", card) == (
        "创作流水线已收口，成品标识=t-final（标题：夏日晚风），"
        "成品全文已交付用户，内容如下：\n\n正文全文"
    )
    assert CANCELLED_PIPELINE_RECEIPT == "创作流水线已被用户放弃，本次未交付成品"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
