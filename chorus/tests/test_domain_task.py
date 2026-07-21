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
    CANCELLABLE_STATUSES,
    LEGAL_TRANSITIONS,
    PostCard,
    PostImage,
    PostSection,
    TERMINAL_STATUSES,
    Task,
    TaskContent,
    TaskPlan,
    TaskProgress,
    TaskStatus,
    StepSpec,
    ValidationError,
    build_task_graph,
    dump_task_graph,
    is_legal_transition,
    select_display_pipeline,
    topological_order,
    IdeaArtifacts,
    IdeaCandidate,
    ScriptArtifacts,
    ScriptBlock,
    TaskArtifacts,
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
        PostSection(kind="caption", text="x")  # type: ignore[arg-type]


def test_legal_transitions_table():
    # 终态不可再转移
    assert not any(f == TaskStatus.FINISHED for f, _ in LEGAL_TRANSITIONS)
    # 关键转移都在
    assert is_legal_transition("pending", "running")
    assert is_legal_transition("running", "awaiting_confirm")
    assert is_legal_transition("awaiting_confirm", "finished")
    assert is_legal_transition("awaiting_confirm", "pending")  # retry
    assert is_legal_transition("failed", "pending")  # retry 复活
    # 批量取消只翻非运行态：运行中不可中途停
    assert is_legal_transition("pending", "cancelled")
    assert is_legal_transition("awaiting_confirm", "cancelled")
    assert not is_legal_transition("running", "cancelled")
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
    assert CANCELLABLE_STATUSES == frozenset({"pending", "awaiting_confirm"})  # 运行中不可中途停
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
    assert node["progress"]["activity_line"] == "作画"
    # 角色差异：选题官思考态台词与配图官不同
    idea_task = _mk(TaskStatus.RUNNING, id="idea", agent_type="idea")
    idea_prog = TaskProgress(task_id="idea", activity_kind="thinking")
    idea_graph = build_task_graph("p", [idea_task], {}, {"idea": idea_prog}, {}, True)
    assert dump_task_graph(idea_graph)["tasks"][0]["progress"]["activity_line"] == "先翻翻最近的热点"


def test_validate_steps_ok():
    steps = [
        StepSpec(agent_type="idea", deps=[]),
        StepSpec(agent_type="script", deps=[0]),
        StepSpec(agent_type="image", deps=[1]),
        StepSpec(agent_type="finalize", deps=[0, 1, 2]),
    ]
    TaskPlan(session_id="s", intent=Intent(topic="t"), steps=steps)  # 构造即校验，不抛


def test_validate_steps_rejects():
    # 漏 finalize
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t"),
                 steps=[StepSpec("idea", [])])
    # 杜撰角色
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t"),
                 steps=[StepSpec("novideo", []), StepSpec("finalize", [0])])
    # 前向依赖
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t"),
                 steps=[StepSpec("idea", [1]), StepSpec("finalize", [0])])
    # 自指
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t"),
                 steps=[StepSpec("idea", [0]), StepSpec("finalize", [0])])
    # 非首步无依赖
    with pytest.raises(ValidationError):
        TaskPlan(session_id="s", intent=Intent(topic="t"), steps=[
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
    tasks = [t for t, _ in pairs]
    contents = [c for _, c in pairs]
    assert all(t.status == TaskStatus.PENDING for t in tasks)
    assert all(t.session_id == "sess-x" and t.created_at == 1000.0 for t in tasks)
    assert tasks[0].dependencies == []
    assert tasks[1].dependencies == [tasks[0].id]
    assert all(t.pipeline_id == tasks[0].pipeline_id for t in tasks)
    # 框架前缀 + 意图 JSON 原文注入调用消息
    assert "创作意图：" in contents[0].invoke_message
    assert "夏日晚风" in contents[0].invoke_message
    # 内容行对齐调度行标识
    assert all(c.task_id == t.id for t, c in pairs)


def test_expand_pipeline_image_progress_total():
    """image 步骤的 progress_total 落进 TaskContent，调度行不携带。"""
    intent = Intent(topic="t", image_count=4)
    steps = [StepSpec("image", []), StepSpec("finalize", [0])]
    pairs = TaskPlan(session_id="s", intent=intent, steps=steps).expand()
    image_task, image_content = next(p for p in pairs if p[0].agent_type == "image")
    assert image_content.progress_total == 4


def test_render_invoke_message_injects_deps_and_feedback():
    content = TaskContent(
        task_id="t", invoke_message="骨架",
        feedback="改标题",
    )
    out = content.render_invoke({"d1": {"title": "x"}}, {"prev": 1})
    assert "骨架" in out
    assert "前置步骤产物" in out
    assert "你上一轮的产物" in out
    assert "用户反馈" in out
    # 无注入时只骨架
    bare = TaskContent(task_id="t", invoke_message="骨架")
    assert bare.render_invoke({}, None) == "骨架"


def test_parse_output_idea_ok():
    content = "### 阳台慢时光\n- 视角：物候\n- 理由：光线挪动"
    artifacts = AGENT_PROFILES["idea"].parse_output(content)
    assert len(artifacts.candidates) == 1
    assert artifacts.candidates[0].title == "阳台慢时光"


def test_parse_output_finalize_postcard():
    content = ("<!-- preview_ref: web-blog/preview/desktop.html -->\n"
               "<!-- stylesheet_ref: web-blog/preview/desktop.css -->\n\n"
               "# 夏日晚风\n\n一段正文\n\n#标签：#夏天")
    artifacts = AGENT_PROFILES["finalize"].parse_output(content)
    assert artifacts.title == "夏日晚风"


def test_parse_output_abandon_block_raises():
    """任一角色产物为 # 失败 块时抛 AbandonError，携带失败说明。"""
    body = "# 失败\n配图服务持续返回 Error，换写法仍无效"
    for agent_type in ("idea", "script", "image", "finalize"):
        with pytest.raises(AbandonError) as exc:
            AGENT_PROFILES[agent_type].parse_output(body)
        assert exc.value.reason == "配图服务持续返回 Error，换写法仍无效"


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


def test_graph_node_exposes_progress_total():
    """配图分母随内容行透进任务图节点并序列化，前端据此显示共 N 张。"""
    task = _mk(TaskStatus.RUNNING, id="img", agent_type="image")
    content = TaskContent(task_id="img", invoke_message="x", progress_total=3)
    graph = build_task_graph("p", [task], {}, {}, {"img": content}, True)
    node = graph.nodes[0]
    assert node.progress_total == 3
    assert dump_task_graph(graph)["tasks"][0]["progress_total"] == 3


def test_artifact_display_title():
    """产物模型自带展示标题属性：选题取选中候选、文案取首小标题、汇总取成品标题。"""
    idea = IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="夏日晚风", angle="a", reason="r")], selected=0)
    assert idea.display_title == "夏日晚风"
    idea_none = IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="首案", angle="", reason="")], selected=None)
    assert idea_none.display_title == "首案"
    script = ScriptArtifacts(blocks=[ScriptBlock(kind="heading", text="开篇"), ScriptBlock(kind="paragraph", text="x")])
    assert script.display_title == "开篇"
    script_plain = ScriptArtifacts(blocks=[ScriptBlock(kind="paragraph", text="x")])
    assert script_plain.display_title is None
    post = PostCard(title="夏日晚风", sections=[])
    assert post.display_title == "夏日晚风"


def test_graph_node_exposes_title():
    """校样清单标题随产物派生透进任务图节点并序列化。"""
    task = _mk(TaskStatus.FINISHED, id="fin", agent_type="finalize")
    art = TaskArtifacts(task_id="fin", artifacts=PostCard(title="夏日晚风", sections=[]))
    graph = build_task_graph("p", [task], {"fin": art}, {}, {}, False)
    assert graph.nodes[0].title == "夏日晚风"
    assert dump_task_graph(graph)["tasks"][0]["title"] == "夏日晚风"


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


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
