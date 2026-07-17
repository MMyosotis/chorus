#!/usr/bin/env python3
"""HTTP/SSE 传输层 E2E：真起 app + TestClient，钉 /chat 端点 SSE 线协议契约。

不调真实 LLM--monkeypatch supervisor.stream 注入脚本化事件序列，确定性验证
事件经 sse() 序列化成 SSE 数据帧后字段往返无损、顺序保留。传输层契约与 LLM 无关。
临时库隔离（patch DATA_DIR）且跑完自动清理，不写 data/chorus.db。
"""
import atexit
import json
import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import chorus.app as app_module
from chorus.domain.events import (
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    ReasoningEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)


def _build_client():
    """临时库上重建 app，返回 TestClient（带 lifespan 起 scheduler）。"""
    tmp = Path(tempfile.mkdtemp())
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    with patch.object(app_module, "DATA_DIR", tmp):
        app = app_module.create_app()
    return TestClient(app)


def _parse_sse_lines(text: str) -> list[dict]:
    """从 SSE 字节流解出事件载荷列表。"""
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        events.append(json.loads(block[len("data: "):]))
    return events


def _fake_stream_factory(events):
    """造一个替换 supervisor.stream 的函数，原样吐脚本化事件。"""
    def _stream(session_id, message, *, model=None, image_model=None, web_search=None):
        for ev in events:
            yield ev
    return _stream


def _seed_session(client):
    r = client.post("/api/sessions", json={"title": "sse-e2e"})
    return r.json()["id"]


def test_chat_replies_sse_event_sequence():
    """闲聊路径：message_start -> token+ -> done 经 HTTP 序列化往返无损。"""
    client = _build_client()
    sid = _seed_session(client)
    fake_events = [
        MessageStartEvent(id="m1"),
        TokenEvent(content="你"),
        TokenEvent(content="好"),
        DoneEvent(),
    ]
    sup = client.app.state.supervisor_service
    with patch.object(sup, "stream", _fake_stream_factory(fake_events)):
        r = client.post(f"/api/sessions/{sid}/chat", json={"message": "hi"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_lines(r.text)
    assert [e["type"] for e in events] == ["message_start", "token", "token", "done"]
    assert events[0]["id"] == "m1"
    assert events[1]["content"] == "你"
    assert events[3]["type"] == "done"


def test_chat_serializes_tool_call_and_result():
    """工具往返：tool_call(id/name/arguments/display) + tool_result(id/content/duration) 字段不丢。"""
    client = _build_client()
    sid = _seed_session(client)
    fake_events = [
        MessageStartEvent(id="m1"),
        ToolCallEvent(id="c1", name="load_skill", arguments={"name": "x"}, display="加载技能 x"),
        ToolResultEvent(tool_call_id="c1", name="load_skill", content="技能内容", duration_ms=12),
        DoneEvent(),
    ]
    sup = client.app.state.supervisor_service
    with patch.object(sup, "stream", _fake_stream_factory(fake_events)):
        r = client.post(f"/api/sessions/{sid}/chat", json={"message": "load"})
    events = _parse_sse_lines(r.text)
    assert [e["type"] for e in events] == ["message_start", "tool_call", "tool_result", "done"]
    assert events[1]["id"] == "c1"
    assert events[1]["name"] == "load_skill"
    assert events[1]["display"] == "加载技能 x"
    assert events[2]["tool_call_id"] == "c1"
    assert events[2]["duration_ms"] == 12


def test_chat_serializes_reasoning_and_error():
    """reasoning token 与 error 事件经 JSON 序列化中文不转义、字段保留。"""
    client = _build_client()
    sid = _seed_session(client)
    fake_events = [
        MessageStartEvent(id="m1"),
        ReasoningEvent(content="思考中文"),
        ErrorEvent(content="出错了"),
    ]
    sup = client.app.state.supervisor_service
    with patch.object(sup, "stream", _fake_stream_factory(fake_events)):
        r = client.post(f"/api/sessions/{sid}/chat", json={"message": "x"})
    # ensure_ascii=False -> 中文原样出现在字节流
    assert "思考中文" in r.text
    assert "出错了" in r.text
    events = _parse_sse_lines(r.text)
    assert [e["type"] for e in events] == ["message_start", "reasoning", "error"]
    assert events[1]["content"] == "思考中文"
    assert events[2]["content"] == "出错了"


def test_chat_404_unknown_session():
    """会话不存在 -> 404，不进 stream。"""
    client = _build_client()
    sup = client.app.state.supervisor_service
    with patch.object(sup, "stream", _fake_stream_factory([DoneEvent()])):
        r = client.post("/api/sessions/unknown/chat", json={"message": "x"})
    assert r.status_code == 404


def test_chat_isolates_db_from_dev():
    """E2E 用临时库：脚本建的会话不污染 data/chorus.db。"""
    import chorus.config as cfg
    dev_db = cfg.DATA_DIR / "chorus.db"
    before = dev_db.stat().st_size if dev_db.exists() else 0
    client = _build_client()
    _seed_session(client)
    after = dev_db.stat().st_size if dev_db.exists() else 0
    assert before == after, "E2E 写进了开发库 chorus.db"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
