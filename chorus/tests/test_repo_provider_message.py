"""ProviderMessageRepository smoke test：现场表换占位、改写、整段覆写与双表双写。"""
from __future__ import annotations

import uuid6

from chorus.domain.message import ToolMessage, UserMessage
from chorus.repo.message import MessageRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.services.message import MessageService
from chorus.tests._helpers import build_compact_service, fresh_engine, seed_session


def _user(mid: str, content: str) -> UserMessage:
    return UserMessage(id=mid, session_id="s1", created_at=0.0, content=content)


def _tool(tid: str, content: str) -> ToolMessage:
    return ToolMessage(
        id=tid, session_id="s1", created_at=0.0,
        tool_call_id=f"call-{tid}", name="search", content=content,
    )


def _setup():
    engine = fresh_engine()
    seed_session(engine)
    return ProviderMessageRepository(engine)


def test_append_and_list_roundtrip():
    repo = _setup()
    repo.append(_user("m1", "问"))
    repo.append(_tool("m2", "答"))
    rows = repo.list_by_session("s1")
    assert [row.id for row in rows] == ["m1", "m2"]
    assert rows[1].tool_call_id == "call-m2"


def test_elide_swaps_only_listed_ids():
    repo = _setup()
    for idx in range(1, 5):
        repo.append(_tool(f"m{idx}", "长结果" * 40))
    repo.elide("s1", ["m1", "m2"], "[占位]")
    contents = [row.content for row in repo.list_by_session("s1")]
    assert contents[:2] == ["[占位]", "[占位]"]
    assert contents[2] == "长结果" * 40


def test_update_content_hits_row_and_noops_when_absent():
    repo = _setup()
    repo.append(_user("m1", "旧文"))
    repo.update_content("m1", "新文")
    repo.update_content("不存在", "无效果")
    assert repo.list_by_session("s1")[0].content == "新文"


def test_replace_with_summary_clears_and_keeps_single_row():
    repo = _setup()
    repo.append(_user("m1", "问"))
    repo.append(_tool("m2", "答"))
    summary = UserMessage(
        id=str(uuid6.uuid7()), session_id="s1", created_at=1.0, content="[历史压缩摘要]\n全程摘要",
    )
    repo.replace_with_summary("s1", summary)
    rows = repo.list_by_session("s1")
    assert len(rows) == 1
    assert rows[0].content == "[历史压缩摘要]\n全程摘要"


def test_message_service_dual_writes_and_rewrites_both_tables():
    """新消息两表同标识双写，改写工具结果两表同步，前端与模型所见一致。"""
    engine = fresh_engine()
    seed_session(engine)
    msg_repo = MessageRepository(engine)
    provider_repo = ProviderMessageRepository(engine)
    svc = MessageService(msg_repo, provider_repo, _stub_trace(), build_compact_service(engine))
    svc.append_user_message("s1", "问")
    svc.append_tool_message("s1", tool_call_id="c1", name="search", content="原始结果")
    svc.rewrite_last_tool_result("s1", "search", "改写后结果")
    raw = msg_repo.list_by_session("s1")
    view = provider_repo.list_by_session("s1")
    assert [row.content for row in raw] == ["问", "改写后结果"]
    assert [row.content for row in view] == ["问", "改写后结果"]


def _stub_trace():
    import types
    return types.SimpleNamespace(batch_aggregate=lambda ids: {})


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
