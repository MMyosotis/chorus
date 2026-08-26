"""压缩编排测试：微压缩落表、阈值摘要覆写、重启安全与两表分工契约。"""
from __future__ import annotations

import uuid6

import chorus.services.compact as compact_mod
from chorus.domain.message import AssistantMessage, Message, ToolMessage, UserMessage
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.services.compact import CompactService
from chorus.tests._helpers import build_compact_service, fresh_engine, seed_session


class _LowThreshold:
    """把阈值临时压到极小，触发摘要分支。"""

    def __enter__(self):
        self._saved = compact_mod.COMPACT_THRESHOLD_TOKENS
        compact_mod.COMPACT_THRESHOLD_TOKENS = 1
        return self

    def __exit__(self, *exc):
        compact_mod.COMPACT_THRESHOLD_TOKENS = self._saved


class _FixedLlm:
    def __init__(self):
        self.calls = 0

    def summarize(self, messages):
        self.calls += 1
        return "固定摘要"


def _build():
    engine = fresh_engine()
    seed_session(engine)
    msg_repo = MessageRepository(engine)
    provider_repo = ProviderMessageRepository(engine)
    return engine, msg_repo, provider_repo, build_compact_service(engine)


def _append_both(msg_repo, provider_repo, msg: Message):
    """模拟生产双写：原始表与现场表同标识各落一行。"""
    msg_repo.append(msg)
    provider_repo.append(msg)


def _seed_rounds(msg_repo, provider_repo, rounds: int) -> None:
    """连续落提问 / 带工具调用的助手 / 工具结果三件套。"""
    for round_idx in range(rounds):
        call_id = f"call-{round_idx}"
        _append_both(msg_repo, provider_repo, UserMessage(
            id=str(uuid6.uuid7()), session_id="s1", created_at=float(round_idx),
            content=f"第{round_idx}轮提问",
        ))
        _append_both(msg_repo, provider_repo, AssistantMessage(
            id=str(uuid6.uuid7()), session_id="s1", created_at=float(round_idx),
            content=None, tool_calls=[_spec(call_id)],
        ))
        _append_both(msg_repo, provider_repo, ToolMessage(
            id=str(uuid6.uuid7()), session_id="s1", created_at=float(round_idx),
            tool_call_id=call_id, name="baidu_search", content="x" * 300,
        ))


def _spec(call_id: str):
    from chorus.domain.message import ToolCallSpec
    return ToolCallSpec(id=call_id, name="baidu_search", arguments_json="{}")


def test_ensure_active_compacts_and_persists_summary_row():
    engine, msg_repo, provider_repo, compact = _build()
    for idx in range(4):
        msg = UserMessage(id=str(uuid6.uuid7()), session_id="s1", created_at=float(idx), content=f"第{idx}条")
        _append_both(msg_repo, provider_repo, msg)
    with _LowThreshold():
        active = compact.ensure_active("s1")
    # 现场只剩摘要行（普通用户消息），原表四条原文一字不动
    assert [m.role for m in active] == ["user"]
    assert active[0].content == "[历史压缩摘要]\n固定摘要"
    assert [m.content for m in msg_repo.list_by_session("s1")] == [f"第{idx}条" for idx in range(4)]


def test_service_restarts_stateless():
    """服务无内存状态：重启即新建实例，现场照常从库恢复。"""
    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="旧消息"))
    with _LowThreshold():
        compact.ensure_active("s1")
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=9.0, content="新消息"))
    rebuilt = CompactService(ProviderMessageRepository(engine), _FixedLlm())
    active = rebuilt.ensure_active("s1")
    assert active[0].role == "user"
    assert active[-1].content == "新消息"


def test_ensure_active_reuses_summary_without_recompacting():
    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="旧消息"))
    with _LowThreshold():
        compact.ensure_active("s1")
    summary_id = provider_repo.list_by_session("s1")[0].id
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=9.0, content="新消息"))
    active = compact.ensure_active("s1")
    # 摘要行仍是既有那一条（未重复生成），新消息跟随其后
    assert active[0].id == summary_id
    assert active[-1].content == "新消息"


def test_micro_elides_old_tools_in_place_keeping_pairs():
    engine, msg_repo, provider_repo, compact = _build()
    _seed_rounds(msg_repo, provider_repo, 5)
    active = compact.ensure_active("s1")
    # 最近 3 条工具结果保留全文，更早两条现场表正文已换成占位；原表原文一字未改
    stored_tools = [m for m in msg_repo.list_by_session("s1") if m.role == "tool"]
    assert all(m.content == "x" * 300 for m in stored_tools)
    view_tools = [m for m in active if m.role == "tool"]
    assert [m.tool_call_id for m in view_tools] == [f"call-{idx}" for idx in range(5)]
    assert [m.content for m in view_tools[:2]] == ["[旧工具结果已省略]"] * 2
    assert all(m.content == "x" * 300 for m in view_tools[2:])
    # 占位已物理落表，重读现场表结果一致
    reread = [m for m in provider_repo.list_by_session("s1") if m.role == "tool"]
    assert [m.content for m in reread] == [m.content for m in view_tools]


def test_repeated_ensure_active_stays_stable_with_paired_tools():
    """长会话连调多次现场不漂移，且不残留没有工具调用与之对应的孤立结果。"""
    engine, msg_repo, provider_repo, compact = _build()
    _seed_rounds(msg_repo, provider_repo, 25)
    runs = [compact.ensure_active("s1") for _ in range(3)]
    assert [len(active) for active in runs] == [len(runs[0])] * 3
    for active in runs:
        offered = {call.id for msg in active if msg.role == "assistant" for call in msg.tool_calls}
        assert all(msg.tool_call_id in offered for msg in active if msg.role == "tool")


def test_summary_supersedes_elided_tools():
    """摘要覆写后现场只剩一行，先前换过占位的工具行不再捞回。"""
    engine, msg_repo, provider_repo, compact = _build()
    _seed_rounds(msg_repo, provider_repo, 5)
    compact.ensure_active("s1")
    with _LowThreshold():
        active = compact.ensure_active("s1")
    assert [m.role for m in active] == ["user"]
    assert all(m.content == "x" * 300 for m in msg_repo.list_by_session("s1") if m.role == "tool")


def test_reactive_forces_compact_below_threshold():
    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="内容"))
    assert compact.reactive("s1") is True
    assert provider_repo.list_by_session("s1")[-1].role == "user"
    assert compact.ensure_active("s1")[0].role == "user"


def test_reactive_twice_rewrites_single_summary_row():
    """每次应急都对全量现场重写摘要；连压两次现场仍只留一行。"""
    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="内容"))
    assert compact.reactive("s1") is True
    assert compact.reactive("s1") is True
    rows = provider_repo.list_by_session("s1")
    assert len(rows) == 1
    assert rows[0].role == "user"


def test_provider_messages_show_summary_while_history_view_reads_original():
    from chorus.repo.trace import TraceRepository
    from chorus.services.message import MessageService
    from chorus.services.trace import TraceService

    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="用户提问"))
    compact.reactive("s1")
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=1.0, content="追问"))

    msg_svc = MessageService(msg_repo, provider_repo, TraceService(TraceRepository(engine)), compact)
    provider = msg_svc.build_provider_messages("s1", "系统提示")
    # 被覆盖行不再发给模型，摘要行以用户消息身份居首
    assert provider[0] == {"role": "system", "content": "系统提示"}
    assert provider[1]["role"] == "user"
    assert "固定摘要" in provider[1]["content"]
    assert provider[-1]["content"] == "追问"

    # 前端视图读原表全量，被覆盖的用户消息照常展示
    views = msg_svc.history_view("s1")
    assert [v.content for v in views] == ["用户提问", "追问"]


def test_memory_extract_source_untouched():
    """记忆提取读原表尾部，原文不受压缩影响。"""
    engine, msg_repo, provider_repo, compact = _build()
    _append_both(msg_repo, provider_repo, UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=0.0, content="我喜欢清爽风格"))
    compact.reactive("s1")
    tail = msg_repo.list_by_session("s1")[-10:]
    user_tail = [m for m in tail if m.role == "user"]
    assert user_tail[-1].content == "我喜欢清爽风格"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
