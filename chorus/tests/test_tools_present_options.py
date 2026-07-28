"""PresentOptionsTool 契约：成功->Suspend+伴随事件+落库；参数错->Reply；resolve_external 回执与关闭。"""
from __future__ import annotations

from chorus.domain.events import OptionPromptEvent
from chorus.repo.option import OptionPromptRepository
from chorus.repo.session import SessionRepository
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.tests._helpers import fresh_conn, seed_session
from chorus.tools.builtin.present_options import PresentOptionsTool
from chorus.tools.framework import Reply, Suspend, ToolContext


def _build():
    conn = fresh_conn()
    seed_session(conn, sid="s1")
    option = OptionPromptService(OptionPromptRepository(conn), SessionService(SessionRepository(conn)))
    tool = PresentOptionsTool(option)
    ctx = ToolContext(session_id="s1")
    return conn, option, tool, ctx


def _args(question="选哪个方向", options=None, allow_custom=True):
    if options is None:
        options = [
            {"label": "咖啡馆探店", "description": "走访三家特色咖啡馆"},
            {"label": "居家咖啡器具", "description": "手冲器具评测"},
            {"label": "咖啡豆产地游", "description": "溯源庄园走访"},
        ]
    return {"question": question, "options": options, "allow_custom": allow_custom}


def test_success_returns_suspend_with_event_and_persists():
    _, option, tool, ctx = _build()
    res = tool.run(_args(), ctx)
    assert isinstance(res.outcome, Suspend)
    assert len(res.events) == 1
    event = res.events[0]
    assert isinstance(event, OptionPromptEvent)
    assert event.question == "选哪个方向"
    assert [o["label"] for o in event.options] == ["咖啡馆探店", "居家咖啡器具", "咖啡豆产地游"]
    assert event.options[0]["signal"] == "0"
    assert event.allow_custom is True
    prompt = option.get_open("s1")
    assert prompt is not None


def test_missing_args_returns_reply():
    _, _, tool, ctx = _build()
    res = tool.run({"question": "x"}, ctx)
    assert isinstance(res.outcome, Reply)
    assert "参数" in res.outcome.content


def test_resolve_external_known_signal_returns_label():
    _, option, tool, ctx = _build()
    tool.run(_args(), ctx)
    receipt = tool.resolve_external("s1", "1", None)
    assert receipt == "用户选择了：居家咖啡器具"
    assert option.get_open("s1") is None


def test_resolve_external_custom_signal_returns_text():
    _, option, tool, ctx = _build()
    tool.run(_args(), ctx)
    receipt = tool.resolve_external("s1", "__custom__", {"custom_text": "我想写冷萃"})
    assert receipt == "用户自由补充：我想写冷萃"
    assert option.get_open("s1") is None


def test_resolve_external_unknown_signal_closes_and_hints():
    _, option, tool, ctx = _build()
    tool.run(_args(), ctx)
    receipt = tool.resolve_external("s1", "9", None)
    assert "无法识别" in receipt
    assert option.get_open("s1") is None


def test_resolve_external_no_open_prompt():
    _, _, tool, _ = _build()
    receipt = tool.resolve_external("s1", "0", None)
    assert "没有待选" in receipt


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
