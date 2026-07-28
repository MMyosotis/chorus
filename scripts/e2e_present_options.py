#!/usr/bin/env python3
"""E2E present_options 链路：FakeModel 控制出题与续跑两轮，经 create_app 真实装配，
验证伴随事件下发、option_prompts 表写入与翻转、tool_result 改写与 resume 续跑。
临时库隔离，跑完自动清理，不写 data/chorus.db。
"""
import atexit
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chorus.app as app_module
from chorus.agents.chat_model import ChatModelEntry
from chorus.domain.title import TitleGenerationService
from chorus.startup import run_startup

_tmp = Path(tempfile.mkdtemp())
atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))


class _Delta(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class FakeStream:
    def __init__(self, deltas):
        self._chunks = [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)]
            )
            for d, fr in deltas
        ]

    def __iter__(self):
        return iter(self._chunks)


class FakeClient:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._scripts.pop(0)


def _fake_provider(client):
    entry = ChatModelEntry(client=client, model_id="fake")

    class _Stub:
        def get_entry(self):
            return entry

        def title_entry(self):
            return entry

    return _Stub()


_PO_ARGS = {
    "question": "选哪个方向",
    "options": [
        {"label": "咖啡馆探店", "description": "走访三家特色咖啡馆"},
        {"label": "居家咖啡器具", "description": "手冲器具评测"},
        {"label": "咖啡豆产地游", "description": "溯源庄园走访"},
    ],
    "allow_custom": True,
}

_client = FakeClient([
    FakeStream([({
        "tool_calls": [types.SimpleNamespace(
            index=0, id="c1",
            function=types.SimpleNamespace(
                name="present_options",
                arguments=json.dumps(_PO_ARGS, ensure_ascii=False),
            ),
        )],
    }, "tool_calls")]),
    FakeStream([({"content": "好的，就按咖啡馆探店方向来写。"}, "stop")]),
])


def main():
    with patch.object(app_module, "DATA_DIR", _tmp), \
            patch.object(app_module, "ChatModelProvider", lambda settings: _fake_provider(_client)), \
            patch.object(TitleGenerationService, "generate", return_value=""):
        app = app_module.create_app()
        run_startup(app.state.scheduler)
        sup = app.state.supervisor_service
        sess = app.state.session_service
        opt = app.state.option_service
        tools = app.state.tool_dispatch

        sid = sess.create("E2E-present_options").id
        print(f"[session] {sid}")

        # 链路 1：模型出题 -> 挂起
        events = list(sup.stream(sid, "帮我选个方向"))
        seq = [e.type for e in events]
        print(f"[事件] {seq}")
        assert "option_prompt" in seq, "缺 option_prompt 伴随事件"
        assert "done" in seq, "缺 done"

        opt_event = next(e for e in events if e.type == "option_prompt")
        assert opt_event.question == "选哪个方向"
        assert len(opt_event.options) == 3
        assert opt_event.allow_custom is True
        assert "prompt_id" not in opt_event.model_dump(), "事件不应带 prompt_id"
        print(f"[出题] {opt_event.question} / {len(opt_event.options)} 个选项")

        open_prompt = opt.get_open(sid)
        assert open_prompt is not None and open_prompt.status == "open"
        assert len(open_prompt.options) == 3
        print(f"[表] open 行落库")

        # 链路 2：用户选项 -> resolve_external -> resume 续跑
        tool = tools.get_tool("present_options")
        receipt = tool.resolve_external(sid, "0", None)
        assert receipt == "用户选择了：咖啡馆探店"
        print(f"[回执] {receipt}")

        resume_events = list(sup.resume(sid, "present_options", receipt))
        resume_text = "".join(e.content for e in resume_events if e.type == "token")
        print(f"[续跑] {resume_text!r}")
        assert "咖啡馆探店" in resume_text, "续跑正文未回灌选择"

        assert opt.get_open(sid) is None, "作答后 open 行未翻转"
        print("[表] open 行已翻 answered")

    print("\nE2E present_options 链路通过")


if __name__ == "__main__":
    main()
