"""会话视图装配纯函数测试：助手轮次合并、卡片锚点插入、留档回看折叠与阶段派生。

合并场景自前端 mergeAssistantHistory 测试移植，挂起宿主判定由工具参数解析改为留档锚点。
"""
from __future__ import annotations

from chorus.domain.intent import IntentConfirmation, IntentConfirmationAnswer, IntentState
from chorus.domain.message import MessageView
from chorus.domain.option import OptionItem, OptionPrompt, OptionQuestion
from chorus.domain.task.graph import TaskGraph, build_task_graph
from chorus.domain.task.models import Task
from chorus.domain.task.products import DeliveredProduct
from chorus.domain.trace import ToolInvocation
from chorus.domain.session.view import build_session_view


def _tool(name: str, arguments: dict | None = None) -> ToolInvocation:
    return ToolInvocation(
        tool_call_id=f"call-{name}", name=name, arguments=arguments or {},
        display=name, duration_ms=10, content="ok",
    )


def _assistant(mid: str, content: str = "", tools: list[ToolInvocation] | None = None) -> MessageView:
    return MessageView(id=mid, role="assistant", content=content, tools=tools or [])


def _user(mid: str, content: str) -> MessageView:
    return MessageView(id=mid, role="user", content=content)


def _state() -> IntentState:
    return IntentState(session_id="s1", image_count=0)


def _confirmation(cid: str, mid: str | None, status: str = "answered") -> IntentConfirmation:
    return IntentConfirmation(
        confirmation_id=cid, session_id="s1", message_id=mid, status=status,
        topic="城市夜骑", platform="小红书", format="图文笔记", style="轻松", image_count=3,
        answer=IntentConfirmationAnswer(signal="confirm", label="确认创作") if status == "answered" else None,
    )


def _prompt(pid: str, mid: str | None, status: str = "answered") -> OptionPrompt:
    return OptionPrompt(
        prompt_id=pid, session_id="s1", message_id=mid, status=status,
        questions=[OptionQuestion(question="选方向", options=[
            OptionItem(signal="1", label="生活感悟", description="记录日常体验"),
            OptionItem(signal="2", label="城市观察", description="关注城市情绪"),
            OptionItem(signal="3", label="探店攻略", description="提供实用信息"),
        ])],
    )


def _task(tid: str, agent_type: str, status: str, mid: str | None = None, deps: list[str] | None = None) -> Task:
    return Task(
        id=tid, session_id="s1", pipeline_id="p1", agent_type=agent_type, status=status,
        created_at=0.0, updated_at=0.0, message_id=mid, dependencies=deps or [],
    )


def _empty_graph():
    return build_task_graph(None, [], {}, {}, {}, False)


def _view(messages, graph=None, products=None, confirmations=None, prompts=None):
    return build_session_view(
        messages, graph if graph is not None else _empty_graph(),
        products or [], _state(), confirmations or [], prompts or [],
    )


def _bubbles(messages, confirmations=None, prompts=None):
    return _view(messages, confirmations=confirmations, prompts=prompts)["bubbles"]


def test_empty_messages_produce_no_bubbles():
    """空入空出。"""
    assert _bubbles([]) == []


def test_tool_turn_without_content_hosts_following_text():
    """段内无正文工具轮作为后续正文的宿主保留。"""
    out = _bubbles([
        _assistant("m1", tools=[_tool("baidu_search")]),
        _assistant("m2", "结果"),
    ])
    assert len(out) == 1
    assert out[0]["content"] == "结果"
    assert out[0]["thinking"] == {"state": "idle", "items": []}
    assert out[0]["tools"]["state"] == "idle"
    assert [tool["name"] for tool in out[0]["tools"]["items"]] == ["baidu_search"]
    assert out[0]["tools"]["items"][0]["id"] == "call-baidu_search"
    assert out[0]["suspended"] is False


def test_user_message_breaks_merge_keeps_suspended_host():
    """用户消息打断后保留前段挂起宿主。"""
    out = _bubbles([
        _assistant("m1", tools=[_tool("baidu_search")]),
        _user("m2", "插话"),
        _assistant("m3", "回复"),
    ])
    assert len(out) == 3
    assert out[0]["suspended"] is True
    assert out[0]["tools"]["items"][0]["name"] == "baidu_search"
    assert out[1]["role"] == "user"
    assert out[1]["content"] == "插话"
    assert out[2]["content"] == "回复"


def test_following_turns_merge_content_and_tools():
    """同气泡后续轮正文与工具均追加。"""
    out = _bubbles([
        _assistant("m1", "首段", [_tool("a")]),
        _assistant("m2", "次段", [_tool("b")]),
    ])
    assert len(out) == 1
    assert out[0]["content"] == "首段\n\n次段"
    assert [tool["name"] for tool in out[0]["tools"]["items"]] == ["a", "b"]


def test_option_host_anchor_merges_follow_ups():
    """选项卡锚点轮后的续写合并回同一气泡。"""
    out = _bubbles(
        [
            _user("m0", "开始创作"),
            _assistant("direction-choice", "请选择一个方向。", [_tool("present_options")]),
            _assistant("m2", "已选生活感悟，接下来补充平台。", [_tool("update_intent_state")]),
            _assistant("platform-choice", "请选择发布平台。", [_tool("present_options")]),
        ],
        prompts=[_prompt("p1", "platform-choice")],
    )
    assert len(out) == 2
    assert out[1]["id"] == "direction-choice"
    assert out[1]["content"] == "请选择一个方向。\n\n已选生活感悟，接下来补充平台。\n\n请选择发布平台。"
    assert [tool["name"] for tool in out[1]["tools"]["items"]] == [
        "present_options", "update_intent_state", "present_options",
    ]
    assert out[1]["suspended"] is True
    assert "platform-choice" in out[1]["message_ids"]


def test_failed_option_call_leaves_no_open_host():
    """未留档的选项工具轮不构成挂起宿主，续写照常合并。"""
    out = _bubbles([
        _user("m0", "写一篇小红书"),
        _assistant("m1", "你更倾向于哪种体裁？"),
        _assistant("m2", tools=[_tool("present_options")]),
        _assistant("m3", "抱歉，刚才工具调用参数没填全。重来——\n\n你更倾向于哪种体裁？"),
    ])
    assert len(out) == 2
    assert "抱歉，刚才工具调用参数没填全" in out[1]["content"]
    assert [tool["name"] for tool in out[1]["tools"]["items"]] == ["present_options"]


def test_tail_tool_turn_merges_into_current_bubble():
    """尾部无正文工具轮合并到当前助手气泡。"""
    out = _bubbles([
        _user("m0", "问"),
        _assistant("m1", "答", [_tool("a")]),
        _assistant("m2", tools=[_tool("tail")]),
    ])
    assert len(out) == 2
    assert out[1]["content"] == "答"
    assert [tool["name"] for tool in out[1]["tools"]["items"]] == ["a", "tail"]


def test_tool_turn_without_content_stays_suspended():
    """无正文工具轮前无助手时保留挂起宿主。"""
    out = _bubbles([
        _user("m0", "问"),
        _assistant("m1", tools=[_tool("only_tool")]),
    ])
    assert len(out) == 2
    assert out[0]["role"] == "user"
    assert out[1]["content"] == ""
    assert out[1]["suspended"] is True
    assert out[1]["tools"]["items"][0]["name"] == "only_tool"


def test_tool_turn_after_user_starts_new_segment():
    """跨用户段的无正文工具轮保留在新段。"""
    out = _bubbles([
        _assistant("m0", "答", [_tool("a")]),
        _user("m1", "再问"),
        _assistant("m2", tools=[_tool("b")]),
    ])
    assert len(out) == 3
    assert out[0]["content"] == "答"
    assert [tool["name"] for tool in out[0]["tools"]["items"]] == ["a"]
    assert out[1]["role"] == "user"
    assert out[2]["content"] == ""
    assert out[2]["suspended"] is True
    assert [tool["name"] for tool in out[2]["tools"]["items"]] == ["b"]


def test_plan_boundary_splits_closing_turn():
    """建图挂起后的按铃收尾另起气泡。"""
    messages = [
        _user("m0", "帮我写"),
        _assistant("m1", "收到，我先安排。"),
        _assistant("plan-turn", tools=[_tool("create_plan")]),
        _assistant("closing-turn", "成品已在下方卡片交付。"),
    ]
    graph = build_task_graph(
        "p1", [_task("t-final", "finalize", "finished", "plan-turn")], {}, {}, {}, False,
    )
    out = _view(messages, graph=graph)["bubbles"]
    assert len(out) == 3
    assert out[1]["content"] == "收到，我先安排。"
    assert out[1]["suspended"] is True
    assert "plan-turn" in out[1]["message_ids"]
    assert out[2]["content"] == "成品已在下方卡片交付。"
    assert out[2]["suspended"] is False
    assert "plan-turn" not in out[2]["message_ids"]


def test_intent_confirm_anchor_keeps_merge():
    """意图确认锚点挂起后的续写仍合并同气泡。"""
    out = _bubbles(
        [
            _user("m0", "写一篇"),
            _assistant("confirm-turn", "请确认创作方向。", [_tool("update_intent_state")]),
            _assistant("m2", "已确认，开始创作。"),
        ],
        confirmations=[_confirmation("c1", "confirm-turn")],
    )
    assert len(out) == 2
    assert out[1]["content"] == "请确认创作方向。\n\n已确认，开始创作。"


def test_merge_splits_at_user_messages():
    """段内工具轮合并，跨用户消息保持分段。"""
    out = _bubbles([
        _assistant("m0", "首答", [_tool("a")]),
        _assistant("m1", tools=[_tool("b")]),
        _user("m2", "再问"),
        _assistant("m3", "再答", [_tool("c")]),
        _assistant("m4", tools=[_tool("d")]),
    ])
    assert len(out) == 3
    assert out[0]["content"] == "首答"
    assert [tool["name"] for tool in out[0]["tools"]["items"]] == ["a", "b"]
    assert out[1]["role"] == "user"
    assert out[2]["content"] == "再答"
    assert [tool["name"] for tool in out[2]["tools"]["items"]] == ["c", "d"]


def test_cards_planned_by_status_and_anchored_after_host():
    """任务卡按状态投影并插在锚点气泡之后。"""
    messages = [
        _user("m0", "帮我写"),
        _assistant("anchor-msg", "安排好了，流水线跑起来了。", [_tool("create_plan")]),
    ]
    graph = build_task_graph("p1", [
        _task("t-idea", "idea", "finished", "anchor-msg", []),
        _task("t-script", "script", "running", "anchor-msg", ["t-idea"]),
        _task("t-image", "image", "awaiting_confirm", "anchor-msg", ["t-script"]),
        _task("t-final", "finalize", "pending", "anchor-msg", ["t-image"]),
    ], {}, {}, {}, True)
    out = _view(messages, graph=graph)
    bubbles = out["bubbles"]
    kinds = [(entry["kind"], entry["id"]) for entry in bubbles]
    assert kinds == [
        ("user", "m0"),
        ("assistant", "anchor-msg"),
        ("confirmed", "confirmed:t-idea"),
        ("running", "running:t-script"),
        ("hil", "hil:t-image"),
    ]
    assert bubbles[2]["anchor_message_id"] == "anchor-msg"
    assert bubbles[2]["task"]["agent_type"] == "idea"
    assert bubbles[3]["task"]["status"] == "running"
    assert bubbles[4]["task"]["status"] == "awaiting_confirm"


def test_failed_task_becomes_recovery_card():
    """失败任务投影成恢复卡。"""
    messages = [_assistant("anchor-msg", "出问题了。")]
    graph = build_task_graph("p1", [_task("t-image", "image", "failed", "anchor-msg")], {}, {}, {}, True)
    bubbles = _view(messages, graph=graph)["bubbles"]
    assert bubbles[1]["kind"] == "recovery"
    assert bubbles[1]["id"] == "recovery:t-image"
    assert bubbles[1]["task"]["error"] is None


def test_product_cards_carry_delivered_content():
    """成品卡使用独立契约承载交付全文，不伪造任务。"""
    messages = [_assistant("anchor-msg", "成品交付。")]
    graph = build_task_graph("p1", [_task("t-final", "finalize", "finished", "anchor-msg")], {}, {}, {}, False)
    products = [DeliveredProduct(id="t-final", message_id="anchor-msg", title="夜骑指南", markdown="# 夜骑", created_at=0.0)]
    bubbles = _view(messages, graph=graph, products=products)["bubbles"]
    product_cards = [entry for entry in bubbles if entry["kind"] == "product"]
    assert len(product_cards) == 1
    card = product_cards[0]
    assert card["id"] == "product:t-final"
    assert card["product"] == {
        "id": "t-final",
        "message_id": "anchor-msg",
        "title": "夜骑指南",
        "markdown": "# 夜骑",
        "created_at": 0.0,
    }


def test_answered_recaps_fold_into_anchor_bubble():
    """已作答留档折进锚点气泡，待作答的不折。"""
    messages = [
        _user("m0", "写一篇"),
        _assistant("m-confirm", "请确认创作方向。"),
        _user("m1", "确认，继续"),
        _assistant("m-option", "请选择发布平台。"),
    ]
    out = _bubbles(
        messages,
        confirmations=[
            _confirmation("c-open", "m-confirm", status="open"),
            _confirmation("c-done", "m-confirm", status="answered"),
        ],
        prompts=[_prompt("p-done", "m-option", status="answered")],
    )
    assert [recap["id"] for recap in out[1]["recaps"]] == ["intent-confirm:c-done"]
    recap = out[1]["recaps"][0]["intent_state"]
    assert recap["confirmation_id"] == "c-done"
    assert recap["answer"]["signal"] == "confirm"
    assert [recap["id"] for recap in out[3]["recaps"]] == ["option:p-done"]
    assert out[3]["recaps"][0]["option_prompt"]["prompt_id"] == "p-done"


def test_view_envelope_fields():
    """信箱字段：意图状态、打开的门禁单、任务图与阶段。"""
    messages = [_assistant("m1", "请确认。")]
    graph = build_task_graph("p1", [_task("t-idea", "idea", "running", "m1")], {}, {}, {}, True)
    out = _view(
        messages, graph=graph,
        confirmations=[_confirmation("c-open", "m1", status="open")],
        prompts=[_prompt("p-open", "m1", status="open")],
    )
    assert out["intent_state"]["session_id"] == "s1"
    assert out["open_confirmation"]["confirmation_id"] == "c-open"
    assert out["open_option_prompt"]["prompt_id"] == "p-open"
    assert out["graph"]["pipeline_id"] == "p1"
    assert out["graph"]["active"] is True
    assert out["stage"] == "等待选择"


def test_stage_gate_overrides_tasks():
    """开放门禁优先派生等待文案，选项门先于确认门，无门禁回落任务态。"""
    messages = [_assistant("m1", "正文")]
    graph = build_task_graph("p1", [_task("t1", "idea", "running", "m1")], {}, {}, {}, True)
    both = _view(
        messages, graph=graph,
        confirmations=[_confirmation("c-open", "m1", status="open")],
        prompts=[_prompt("p-open", "m1", status="open")],
    )
    assert both["stage"] == "等待选择"
    confirm_only = _view(messages, graph=graph, confirmations=[_confirmation("c-open", "m1", status="open")])
    assert confirm_only["stage"] == "等待确认"
    assert _view(messages, graph=graph)["stage"] == "选题官 · 执行中"


def test_stage_labels():
    """阶段文案覆盖运行中、待确认、需处理、已完成与自由对话。"""
    cases = [
        ("running", "idea", "选题官 · 执行中"),
        ("awaiting_confirm", "script", "文案官 · 等待确认"),
        ("failed", "image", "配图官 · 需要处理"),
        ("finished", "finalize", "已完成"),
        ("pending", "idea", "自由对话"),
    ]
    for status, agent_type, expected in cases:
        graph = build_task_graph("p1", [_task("t1", agent_type, status, "m1")], {}, {}, {}, True)
        out = _view([_assistant("m1", "正文")], graph=graph)
        assert out["stage"] == expected


def test_stage_priority_is_independent_of_task_order():
    """多任务并存时按显式状态与角色优先级选阶段。"""
    tasks = [
        _task("t-running-image", "image", "running", "m1"),
        _task("t-failed-script", "script", "failed", "m1"),
        _task("t-failed-idea", "idea", "failed", "m1"),
    ]
    forward = build_task_graph("p1", tasks, {}, {}, {}, True)
    backward_graph = build_task_graph("p1", tasks, {}, {}, {}, True)
    backward = TaskGraph(
        pipeline_id=backward_graph.pipeline_id,
        active=backward_graph.active,
        nodes=list(reversed(backward_graph.nodes)),
    )
    messages = [_assistant("m1", "正文")]
    assert _view(messages, graph=forward)["stage"] == "选题官 · 需要处理"
    assert _view(messages, graph=backward)["stage"] == "选题官 · 需要处理"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
