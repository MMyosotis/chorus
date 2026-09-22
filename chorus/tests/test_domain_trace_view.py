"""trace 视图装配纯函数测试：聚合配对 / 轮次切分 / 旁路归属 / 统计折算 / 角色过滤。

只锚定装配纯函数的输入输出契约，不触达 repo 与服务层。
"""
from __future__ import annotations

from chorus.domain.task.models import AgentType
from chorus.domain.trace import build_trace_view
from chorus.domain.trace.aggregation import aggregate_trace
from chorus.domain.trace.models import (
    BypassCall,
    ModelRequest,
    ModelResponse,
    ToolCallSummary,
    TraceEntry,
    TracePhase,
    TraceToolCall,
    TraceToolResult,
    UserInput,
)


def _entry(phase, at, payload, **kwargs):
    return TraceEntry(session_id="s1", phase=phase, created_at=at, payload=payload, **kwargs)


def _request(at, message_id, messages, **kwargs):
    request = ModelRequest(model=kwargs.pop("model", "gpt"), messages=messages, tools=[])
    return _entry(TracePhase.MODEL_REQUEST, at, request, message_id=message_id, **kwargs)


def _response(at, message_id, **kwargs):
    response = ModelResponse(content=kwargs.pop("content", "ok"), **kwargs)
    return _entry(TracePhase.MODEL_RESPONSE, at, response, message_id=message_id)


def _tool_result(at, message_id, call_id="c1", content="r", duration_ms=7, name="search"):
    result = TraceToolResult(tool_call_id=call_id, name=name, content=content, duration_ms=duration_ms)
    return _entry(TracePhase.TOOL_RESULT, at, result, message_id=message_id)


def _tool_call(at, message_id, call_id="c1", name="search"):
    payload = TraceToolCall(tool_call_id=call_id, name=name, arguments={}, display=name)
    return _entry(TracePhase.TOOL_CALL, at, payload, message_id=message_id)


def _bypass(at, purpose, **payload_kwargs):
    payload = BypassCall(purpose=purpose, model="m", prompt="p", max_tokens=512, **payload_kwargs)
    return _entry(TracePhase.BYPASS_CALL, at, payload)


def _kinds(view):
    return [item["kind"] for group in view["turns"] for item in group["items"]]


def test_same_message_out_of_order_entries_pair():
    """同消息标识的乱序轨迹行聚合配对成一次模型调用。"""
    entries = [
        _response(3, "m1"),
        _tool_result(2, "m1"),
        _request(1, "m1", [{"role": "user", "content": "问"}]),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop"]
    group = view["turns"][0]
    loop = group["items"][1]
    assert loop["request"]["messages"][0]["preview"] == "问"
    assert loop["response"]["content"] == "ok"
    assert view["stats"]["turn_count"] == 1


def test_tool_results_backfill_between_loop_items():
    """带工具结果的调用后接现场回灌请求，中间出工具回填行。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1", tool_calls=[ToolCallSummary(tool_call_id="c1", name="search", arguments={})]),
        _tool_result(3, "m1", content='<tool_result>\n{"ok":true}\n</tool_result>'),
        _request(4, "m2", [{"role": "tool", "tool_call_id": "c1", "content": '{"ok":true}'}]),
        _response(5, "m2"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop", "toolback", "loop"]
    toolback = view["turns"][0]["items"][2]
    tool = toolback["tools"][0]
    assert tool["name"] == "search"
    assert tool["content"] == '{"ok":true}'
    assert tool["pretty"] == '{\n  "ok": true\n}'
    assert toolback["total_ms"] == 7


def test_bypass_before_first_turn_joins_it():
    """首轮模型调用前的旁路并入第一轮，不占轮次。"""
    entries = [
        _bypass(1, "memory_recall"),
        _request(2, "m1", [{"role": "user", "content": "问"}]),
        _response(3, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "bypass", "loop"]
    assert len(view["turns"]) == 1
    assert view["turns"][0]["turn"] == 1
    assert view["stats"]["turn_count"] == 1


def test_bypass_between_and_after_turns_inherit_turn():
    """轮间与收尾后的旁路各继承当时轮次。"""
    entries = [
        _request(2, "m1", [{"role": "user", "content": "问一"}]),
        _response(3, "m1"),
        _bypass(3.5, "summary"),
        _request(4, "m2", [{"role": "user", "content": "问二"}]),
        _response(5, "m2"),
        _bypass(6, "title"),
    ]
    view = build_trace_view(entries, {})
    assert [group["turn"] for group in view["turns"]] == [1, 2]
    assert _kinds(view) == ["user", "loop", "bypass", "user", "loop", "bypass"]
    assert view["turns"][0]["items"][2]["purpose_label"] == "历史摘要"
    assert view["turns"][1]["items"][2]["purpose_label"] == "生成标题"


def test_bypass_only_keeps_turn_zero():
    """只有旁路轨迹时占轮 0，不产生对话轮次。"""
    view = build_trace_view([_bypass(1, "suggestion")], {})
    assert len(view["turns"]) == 1
    assert view["turns"][0]["turn"] == 0
    assert view["stats"]["bypass_count"] == 1
    assert view["stats"]["call_count"] == 0
    assert view["stats"]["turn_count"] == 0


def test_empty_trace_has_no_turns():
    assert build_trace_view([], {}) == {"agents": [], "stats": None, "turns": []}


def test_trace_iterator_preserves_user_inputs_and_bypasses():
    entries = [
        _entry(TracePhase.USER_INPUT, 1, UserInput(content="问"), message_id="u1"),
        _bypass(2, "memory_recall"),
        _request(3, "m1", [{"role": "user", "content": "问"}]),
        _response(4, "m1"),
    ]
    assert build_trace_view(iter(entries), {}) == build_trace_view(entries, {})


def test_pending_call_has_no_response_metrics():
    entries = [_request(1, "m1", [{"role": "user", "content": "问"}])]
    view = build_trace_view(entries, {})
    loop = view["turns"][0]["items"][1]
    assert loop["status"] == "pending"
    assert loop["status_label"] == "进行中"
    assert loop["duration_ms"] is None
    assert loop["thinking_ms"] == 0
    assert loop["usage"] is None
    assert loop["cost_cny"] is None
    assert loop["has_output"] is False
    assert loop["response"] is None
    assert loop["request"]["messages"][0]["preview"] == "问"


def test_completed_call_preserves_response_details_and_zero_cost():
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(
            2, "m1", content="", duration_ms=1000, cost_cny=0.0,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            thinking_segments=[{"text": "分析一", "duration_ms": 100}, {"text": "分析二", "duration_ms": 200}],
            tool_calls=[ToolCallSummary(tool_call_id="c1", name="search", arguments={"query": "主题"})],
        ),
    ]
    loop = build_trace_view(entries, {})["turns"][0]["items"][1]
    assert loop["status"] == "success"
    assert loop["status_label"] == "成功"
    assert loop["duration_ms"] == 1000
    assert loop["thinking_ms"] == 300
    assert loop["usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert loop["cost_cny"] == 0.0
    assert loop["has_output"] is True
    assert loop["response"]["content"] == ""
    assert loop["response"]["thinking_segments"] == [
        {"text": "分析一", "duration_ms": 100}, {"text": "分析二", "duration_ms": 200},
    ]
    assert loop["response"]["tools"] == [
        {"id": "c1", "name": "search", "arguments_pretty": '{\n  "query": "主题"\n}'},
    ]
    assert loop["response"]["raw"] == entries[1].payload.model_dump()


def test_failed_call_keeps_error_response_without_output():
    entries = [
        _request(1, "m1", []),
        _response(2, "m1", content="", status="error", error="模型失败"),
    ]
    loop = build_trace_view(entries, {})["turns"][0]["items"][0]
    assert loop["status"] == "error"
    assert loop["status_label"] == "失败"
    assert loop["has_output"] is False
    assert loop["thinking_ms"] == 0
    assert loop["usage"] is None
    assert loop["cost_cny"] is None
    assert loop["response"]["raw"]["error"] == "模型失败"


def test_request_details_preserve_roles_and_raw_payload():
    request = ModelRequest(model="gpt", messages=[
        {"role": "system", "content": "规则"},
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": None, "reasoning_content": "思考", "tool_calls": [{
            "id": "c1", "function": {"name": "search", "arguments": '{"query":"主题"}'},
        }]},
        {"role": "tool", "tool_call_id": "c1", "content": "<tool_result>结果</tool_result>"},
    ], tools=[{"type": "function", "function": {"name": "search", "description": "搜索"}}])
    entries = [
        _request(0, "m0", [{"role": "user", "content": "问题"}]),
        _tool_result(0.5, "m0"),
        _entry(TracePhase.MODEL_REQUEST, 1, request, message_id="m1"),
    ]
    rows = build_trace_view(entries, {})["turns"][0]["items"]
    loop = next(row for row in rows if row["kind"] == "loop" and row["key"] == "m1")
    detail = loop["request"]
    assert detail["model"] == "gpt"
    assert detail["raw"] == request.model_dump()
    assert detail["tools"] == [{"name": "search", "description": "搜索"}]
    assert [message["role"] for message in detail["messages"]] == ["system", "user", "assistant", "tool"]
    assert detail["messages"][0]["preview"] == "规则"
    assert detail["messages"][1]["preview"] == "问题"
    assert detail["messages"][2]["preview"] == "无正文 · think"
    assert detail["messages"][2]["tool_calls"][0]["args_pretty"] == '{\n  "query": "主题"\n}'
    assert detail["messages"][3] == {"role": "tool", "role_label": "tool", "preview": "search", "content": "结果"}


def test_leading_bypasses_join_explicit_turn_before_first_call():
    entries = [
        _bypass(1, "memory_recall", duration_ms=500),
        _entry(TracePhase.USER_INPUT, 2, UserInput(content="问"), message_id="u1"),
        _bypass(3, "summary"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "bypass", "bypass"]
    assert [group["turn"] for group in view["turns"]] == [1]
    assert view["turns"][0]["duration_ms"] == 2500
    assert view["stats"]["turn_count"] == 0

    entries.append(_request(4, "m1", [{"role": "user", "content": "问"}]))
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "bypass", "bypass", "loop"]
    assert view["turns"][0]["agent_name"] == "主编辑"
    assert view["stats"]["turn_count"] == 1


def test_consecutive_inputs_keep_separate_turns():
    entries = [
        _entry(TracePhase.USER_INPUT, 1, UserInput(content="问一"), message_id="u1"),
        _entry(TracePhase.USER_INPUT, 2, UserInput(content="问二"), message_id="u2"),
        _request(3, "m1", [{"role": "user", "content": "问二"}]),
    ]
    view = build_trace_view(entries, {})
    assert [group["turn"] for group in view["turns"]] == [1, 2]
    assert [[item["kind"] for item in group["items"]] for group in view["turns"]] == [
        ["user"], ["user", "loop"],
    ]
    assert view["turns"][0]["agent_name"] == "—"
    assert view["turns"][0]["duration_ms"] == 0
    assert view["stats"]["turn_count"] == 2


def test_first_call_with_only_tool_messages_starts_turn_without_user():
    entries = [
        _bypass(1, "summary"),
        _request(2, "m1", [{"role": "tool", "tool_call_id": "missing", "content": "结果"}]),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["bypass", "loop"]
    assert view["stats"]["turn_count"] == 1


def test_explicit_user_input_uses_real_time_and_parses_injections():
    """显式用户输入行用真实时间并反解注入段，后续调用不再重复出用户行。"""
    entries = [
        _entry(
            TracePhase.USER_INPUT, 1,
            UserInput(content="<memory_summary>摘要</memory_summary>\n真实输入"),
            message_id="u1",
        ),
        _bypass(2, "memory_recall"),
        _request(3, "m1", [{"role": "user", "content": "真实输入"}]),
        _response(4, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "bypass", "loop"]
    user = view["turns"][0]["items"][0]
    assert user["created_at"] == 1
    assert user["text"] == "真实输入"
    assert user["injections"] == [{"label": "记忆摘要", "content": "摘要"}]


def test_implicit_user_input_derived_from_request():
    """无显式输入轨迹时从请求消息回溯出用户行并反解注入段。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "<memory_summary>摘要</memory_summary>\n问"}]),
        _response(2, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop"]
    user = view["turns"][0]["items"][0]
    assert user["created_at"] == 1
    assert user["text"] == "问"
    assert user["injections"] == [{"label": "记忆摘要", "content": "摘要"}]


def test_implicit_input_formats_non_text_content_like_request_details():
    entries = [_request(1, "m1", [{"role": "user", "content": {"topic": "主题"}}])]
    rows = build_trace_view(entries, {})["turns"][0]["items"]
    assert rows[0]["text"] == '{\n  "topic": "主题"\n}'
    assert rows[0]["text"] == rows[1]["request"]["messages"][0]["text"]


def test_latest_user_without_body_does_not_reuse_older_input():
    entries = [_request(1, "m1", [
        {"role": "user", "content": "旧问题"},
        {"role": "assistant", "content": "旧回答"},
        {"role": "user", "content": "<memory_summary>摘要</memory_summary>"},
    ])]
    assert _kinds(build_trace_view(entries, {})) == ["loop"]


def test_first_call_after_explicit_input_stays_in_turn():
    """显式输入后的首个调用直接归入该轮，不再重复开轮。"""
    entries = [
        _entry(TracePhase.USER_INPUT, 1, UserInput(content="问"), message_id="u1"),
        _request(2, "m1", [{"role": "user", "content": "问"}]),
        _response(3, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop"]
    assert view["stats"]["turn_count"] == 1


def test_interleaved_agents_toolback_joins_by_tool_call_id():
    """交错 agent 下回填按调用标识连接归属调用，不再认时间前驱。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}], task_id="t1"),
        _response(2, "m1", tool_calls=[ToolCallSummary(tool_call_id="c1", name="search", arguments={})]),
        _tool_call(2.5, "m1"),
        _tool_result(3, "m1"),
        _request(3.5, "m3", [{"role": "user", "content": "写"}], task_id="t2"),
        _response(4, "m3"),
        _request(5, "m4", [{"role": "tool", "tool_call_id": "c1", "content": '{"ok":true}'}], task_id="t1"),
        _response(6, "m4"),
    ]
    mapping = {"t1": AgentType.IDEA, "t2": AgentType.SCRIPT}
    view = build_trace_view(entries, mapping)
    assert [group["turn"] for group in view["turns"]] == [1, 2]
    assert _kinds(view) == ["user", "loop", "user", "loop", "toolback", "loop"]
    toolback = view["turns"][1]["items"][2]
    tool = toolback["tools"][0]
    assert tool["name"] == "search"
    assert tool["content"] == "r"
    assert toolback["total_ms"] == 7
    request = view["turns"][1]["items"][3]["request"]
    assert request["messages"][0]["content"] == '{"ok":true}'

    filtered = build_trace_view(entries, mapping, agent_key="task:t1")
    assert [group["turn"] for group in filtered["turns"]] == [1]
    assert _kinds(filtered) == ["user", "loop", "toolback", "loop"]
    assert filtered["stats"] == view["stats"]


def test_toolback_selects_only_trailing_ids_in_request_order():
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _tool_result(2, "m1", call_id="old", content="旧结果"),
        _tool_result(3, "m1", call_id="first", content="第一项", duration_ms=3),
        _tool_result(4, "m1", call_id="second", content="第二项", duration_ms=5),
        _response(5, "m1", tool_calls=[ToolCallSummary(tool_call_id="pending", name="search", arguments={})]),
        _request(6, "m2", [
            {"role": "tool", "tool_call_id": "old", "content": "旧结果"},
            {"role": "assistant", "content": "继续"},
            {"role": "tool", "tool_call_id": "second", "content": "第二项"},
            {"role": "tool", "tool_call_id": "pending", "content": "缺结果事件"},
            {"role": "tool", "tool_call_id": "missing", "content": "缺调用事件"},
            {"role": "tool", "tool_call_id": "first", "content": "第一项"},
        ]),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop", "toolback", "loop"]
    toolback = view["turns"][0]["items"][2]
    assert [tool["id"] for tool in toolback["tools"]] == ["second", "first"]
    assert [tool["content"] for tool in toolback["tools"]] == ["第二项", "第一项"]
    assert toolback["total_ms"] == 8


def test_explicit_input_before_tool_continuation_keeps_its_turn():
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问一"}]),
        _tool_result(2, "m1"),
        _entry(TracePhase.USER_INPUT, 3, UserInput(content="问二"), message_id="u2"),
        _request(4, "m2", [{"role": "tool", "tool_call_id": "c1", "content": "r"}]),
        _request(5, "m3", [{"role": "user", "content": "问三"}]),
    ]
    view = build_trace_view(entries, {})
    assert [group["turn"] for group in view["turns"]] == [1, 2, 3]
    assert [[item["kind"] for item in group["items"]] for group in view["turns"]] == [
        ["user", "loop"], ["user", "toolback", "loop"], ["user", "loop"],
    ]


def test_turn_duration_includes_tool_results_after_model_response():
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1", duration_ms=1000),
        _tool_result(4, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert view["turns"][0]["duration_ms"] == 3000
    assert view["stats"]["duration_ms"] == 3000


def test_response_tool_summary_without_tool_events():
    """响应带工具调用摘要但缺工具事件轨迹时，调用行内仍有工具明细、无回填行。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1", tool_calls=[ToolCallSummary(tool_call_id="c1", name="search", arguments={})]),
    ]
    view = build_trace_view(entries, {})
    assert _kinds(view) == ["user", "loop"]
    loop = view["turns"][0]["items"][1]
    assert loop["response"]["tools"] == [{"id": "c1", "name": "search", "arguments_pretty": "{}"}]


def test_result_only_tool_keeps_placeholder_in_message_trace():
    """只有工具结果没有调用事件时，消息聚合仍保留占位工具行。"""
    entries = [_tool_result(1, "m1", content="结果", duration_ms=9)]
    trace = aggregate_trace("m1", entries)
    assert len(trace.tools) == 1
    tool = trace.tools[0]
    assert tool.tool_call_id == "c1"
    assert tool.name == "search"
    assert tool.arguments == {}
    assert tool.display == ""
    assert tool.duration_ms == 9
    assert tool.content == "结果"


def test_response_summary_only_keeps_tool_in_message_trace():
    """只有响应工具摘要没有调用与结果事件时，消息聚合仍保留工具行。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1", tool_calls=[ToolCallSummary(tool_call_id="c1", name="search", arguments={"q": "x"})]),
    ]
    trace = aggregate_trace("m1", entries)
    assert len(trace.tools) == 1
    tool = trace.tools[0]
    assert tool.tool_call_id == "c1"
    assert tool.name == "search"
    assert tool.arguments == {"q": "x"}
    assert tool.display == "search"
    assert tool.duration_ms == 0
    assert tool.content == ""


def test_turn_duration_counts_bypass_interval():
    """轮时长用事件时间区间：旁路结束于完成时刻，开始按自报时长回推。"""
    entries = [
        _request(2, "m1", [{"role": "user", "content": "问"}]),
        _response(3, "m1"),
        _bypass(3.5, "title", duration_ms=500),
    ]
    view = build_trace_view(entries, {})
    assert view["turns"][0]["duration_ms"] == 1500


def test_stats_aggregates_bypass_usage_and_cost():
    """统计折算旁路用量与费用，时长覆盖到最后事件。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1", usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, cost_cny=0.1),
        _bypass(3, "title", usage={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}, cost_cny=0.2),
    ]
    view = build_trace_view(entries, {})
    stats = view["stats"]
    assert stats["input_tokens"] == 17
    assert stats["output_tokens"] == 8
    assert stats["total_tokens"] == 25
    assert abs(stats["cost_cny"] - 0.3) < 1e-9
    assert stats["duration_ms"] == 2000
    assert stats["call_count"] == 1
    assert stats["bypass_count"] == 1


def test_agent_filter_rebuilds_turns_but_keeps_full_stats_and_agents():
    """按角色过滤时间线并重算轮次，角色清单与统计保持全量。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}], task_id="t1"),
        _response(2, "m1", content="idea done"),
        _request(3, "m2", [{"role": "user", "content": "写"}], task_id="t2"),
        _response(4, "m2", content="script done"),
    ]
    mapping = {"t1": AgentType.IDEA, "t2": AgentType.SCRIPT}
    view = build_trace_view(entries, mapping, agent_key="task:t1")
    assert [agent["label"] for agent in view["agents"]] == ["选题", "文案"]
    assert view["stats"]["call_count"] == 2
    assert len(view["turns"]) == 1
    assert _kinds(view) == ["user", "loop"]
    assert view["turns"][0]["agent_name"] == "选题官"
    full = build_trace_view(entries, mapping)
    assert len(full["turns"]) == 2


def test_supervisor_role_labels():
    """supervisor 来源角色：过滤键 supervisor、页签主编、轮次归属主编辑。"""
    entries = [
        _request(1, "m1", [{"role": "user", "content": "问"}]),
        _response(2, "m1"),
    ]
    view = build_trace_view(entries, {})
    assert view["agents"] == [{"key": "supervisor", "label": "主编"}]
    assert view["turns"][0]["agent_name"] == "主编辑"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
