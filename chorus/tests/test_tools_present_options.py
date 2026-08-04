"""PresentOptionsTool 契约：成功->Suspend+伴随事件+落库；参数错->Reply；resolve_external 回执与关闭。"""
from __future__ import annotations

from chorus.domain.events import OptionPromptEvent
from chorus.repo.option import OptionPromptRepository
from chorus.repo.session import SessionRepository
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.tests._helpers import fresh_engine, seed_session
from chorus.tools.builtin.present_options import PresentOptionsTool
from chorus.tools.framework import Reply, Suspend, ToolContext


def _build():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    option = OptionPromptService(OptionPromptRepository(engine), SessionService(SessionRepository(engine)))
    tool = PresentOptionsTool(option)
    ctx = ToolContext(session_id="s1", message_id="m-option")
    return engine, option, tool, ctx


def _options():
    return [
        {"label": "咖啡馆探店", "description": "走访三家特色咖啡馆"},
        {"label": "居家咖啡器具", "description": "手冲器具评测"},
        {"label": "咖啡豆产地游", "description": "溯源庄园走访"},
    ]


def _args(questions=None):
    if questions is None:
        questions = [{
            "question": "选哪个方向",
            "options": _options(),
            "allow_custom": True,
        }]
    return {"questions": questions}


def _batch_args():
    return _args(questions=[
        {
            "question": "选哪个方向",
            "options": _options(),
            "allow_custom": True,
        },
        {
            "question": "选什么风格",
            "options": [
                {"label": "温暖治愈", "description": "有画面感"},
                {"label": "轻松幽默", "description": "更活泼"},
                {"label": "专业干货", "description": "信息更密"},
            ],
            "allow_custom": False,
        },
    ])


def test_success_returns_suspend_with_event_and_persists():
    _, option, tool, ctx = _build()
    res = tool.run(_batch_args(), ctx)
    assert isinstance(res.outcome, Suspend)
    assert len(res.events) == 1
    event = res.events[0]
    assert isinstance(event, OptionPromptEvent)
    assert event.message_id == "m-option"
    assert [question["question"] for question in event.questions] == ["选哪个方向", "选什么风格"]
    assert [option["label"] for option in event.questions[0]["options"]] == ["咖啡馆探店", "居家咖啡器具", "咖啡豆产地游"]
    assert event.questions[0]["options"][0]["signal"] == "0"
    prompt = option.get_open("s1")
    assert prompt is not None
    assert prompt.message_id == "m-option"


def test_missing_args_returns_reply():
    _, _, tool, ctx = _build()
    res = tool.run({"questions": [{}]}, ctx)
    assert isinstance(res.outcome, Reply)
    assert "参数" in res.outcome.content


def test_resolve_external_batch_returns_all_labels_once():
    _, option, tool, ctx = _build()
    tool.run(_batch_args(), ctx)
    receipt = tool.resolve_external("s1", "submit", {"answers": [
        {"signal": "1"},
        {"signal": "0"},
    ]})
    assert receipt == "用户已完成本组选择：选哪个方向：居家咖啡器具；选什么风格：温暖治愈"
    assert option.get_open("s1") is None
    assert [answer.label for answer in option.list_by_session("s1")[0].answers] == ["居家咖啡器具", "温暖治愈"]


def test_resolve_external_custom_signal_returns_text():
    _, option, tool, ctx = _build()
    tool.run(_args(), ctx)
    receipt = tool.resolve_external("s1", "submit", {"answers": [
        {"signal": "__custom__", "custom_text": "我想写冷萃"},
    ]})
    assert receipt == "用户已完成本组选择：选哪个方向：我想写冷萃"
    assert option.get_open("s1") is None
    assert option.list_by_session("s1")[0].answers[0].custom_text == "我想写冷萃"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
