#!/usr/bin/env python3
"""ChatService 顺序契约 smoke test —— 直接调 ChatService.stream，不走 HTTP。

断言 agent loop 的事件序列与入库契约（对齐 CLAUDE.md「顺序契约可测」）。
用 FakeOpenAIStream 脚本化 chunk 流，FakeTool 避免依赖 skill/image，临时 db 隔离。
运行：`.venv/bin/python -m kitty.tests.test_chat_pipeline`
"""

from __future__ import annotations

import tempfile
import types
from pathlib import Path

from kitty.domain.skill import SkillLoader
from kitty.hooks import HookRegistry, RollbackHandler, TraceEmitter
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.message import MessageRepository
from kitty.repositories.session import SessionRepository
from kitty.repositories.trace import TraceRepository
from kitty.services.chat import ChatModelEntry, ChatService
from kitty.services.message import MessageService
from kitty.services.session import SessionService
from kitty.tools import Tool, ToolContext, ToolRegistry


# —— fakes ——

class _Delta(types.SimpleNamespace):
    """容错 delta：访问未设置字段返回 None（模拟 OpenAI SDK pydantic delta 行为）。"""

    def __getattr__(self, name):
        return None


class FakeStream:
    """脚本化 OpenAI chunk 流：按预设的 delta 序列产出。"""

    def __init__(self, deltas: list[tuple[dict, str | None]]):
        # 每项 (delta_attrs, finish_reason)
        self._chunks = [
            types.SimpleNamespace(choices=[
                types.SimpleNamespace(delta=_Delta(**d), finish_reason=fr)
            ])
            for d, fr in deltas
        ]

    def __iter__(self):
        return iter(self._chunks)


class FakeOpenAIClient:
    """按调用次数返回预设流：第 1 次工具轮，第 2 次文本轮。"""

    def __init__(self):
        self._scripts: list[FakeStream] = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def queue_tool_then_text(self, tool_name: str, tool_args: str, tool_call_id: str, text: str) -> None:
        tool_stream = FakeStream([
            ({"tool_calls": [types.SimpleNamespace(
                index=0, id=tool_call_id,
                function=types.SimpleNamespace(name=tool_name, arguments=tool_args),
            )]}, "tool_calls"),
        ])
        text_stream = FakeStream([
            ({"content": text}, "stop"),
        ])
        self._scripts = [tool_stream, text_stream]

    def queue_text(self, text: str) -> None:
        self._scripts = [FakeStream([({"content": text}, "stop")])]

    def _create(self, **kwargs):
        if not self._scripts:
            raise AssertionError("FakeOpenAIClient: 无预设流（调用次数超出预期）")
        return self._scripts.pop(0)


class FakeTool(Tool):
    name = "fake_tool"
    description = "测试用工具"
    parameters = {"type": "object", "properties": {}}

    def run(self, arguments: dict, ctx: ToolContext) -> str:
        return "fake-result"


# —— 装配 ——

def _build_services(db_path: Path):
    conn = ConnectionFactory(db_path)
    session_repo = SessionRepository(conn)
    msg_repo = MessageRepository(conn)
    trace_repo = TraceRepository(conn)
    session_service = SessionService(session_repo)
    message_service = MessageService(msg_repo, trace_repo)
    return session_service, message_service


def _build_chat(session_service, message_service, fake_client):
    skill_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))  # 空目录，无 skill
    skill_loader.load()  # 显式加载空集

    hooks = HookRegistry()
    trace = TraceEmitter(message_service, max_tokens=1024)
    hooks.register("BeforeModelRequest", trace.before_model_request)
    hooks.register("AfterModelResponse", trace.after_model_response)
    hooks.register("PreToolUse", trace.on_tool_call)
    hooks.register("PostToolUse", trace.on_tool_result)
    hooks.register("Error", RollbackHandler(message_service).on_error)

    tool_registry = ToolRegistry([FakeTool()])

    def tool_ctx_factory(session_id, image_model=None):
        return ToolContext(skill_loader=skill_loader, session_id=session_id, image_model=image_model)

    entry = ChatModelEntry(client=fake_client, model_id="fake-model")
    return ChatService(
        session_service, message_service, skill_loader, hooks,
        tool_registry, tool_ctx_factory, {"fake": entry},
        "fake", 1024, tool_registry.schemas_openai(),
    )


# —— 用例 ——

def test_text_turn():
    """用例 A：纯文本轮 —— 事件序列 [message_start, token+, done]，DB 1 user + 1 assistant。"""
    with tempfile.TemporaryDirectory() as tmp:
        session_service, message_service = _build_services(Path(tmp) / "t.db")
        client = FakeOpenAIClient()
        client.queue_text("你好")
        chat = _build_chat(session_service, message_service, client)

        session = session_service.create("test")
        events = list(chat.stream(session.id, "hi"))

        types_seq = [e.type for e in events]
        assert types_seq[0] == "message_start", types_seq
        assert "token" in types_seq, types_seq
        assert types_seq[-1] == "done", types_seq

        msgs = message_service.list_messages(session.id)
        assert len(msgs) == 2, [m.role for m in msgs]
        assert msgs[0].role == "user" and msgs[0].content == "hi"
        assert msgs[1].role == "assistant" and msgs[1].content == "你好"
        print("[A] 纯文本轮 通过")


def test_tool_turn():
    """用例 B：工具轮 —— 事件序列含 [message_start, tool_call, tool_result, message_start, token+, done]，
    DB user + assistant(tool_calls) + tool + assistant(文本)。"""
    with tempfile.TemporaryDirectory() as tmp:
        session_service, message_service = _build_services(Path(tmp) / "t.db")
        client = FakeOpenAIClient()
        client.queue_tool_then_text("fake_tool", "{}", "call-1", "完成")
        chat = _build_chat(session_service, message_service, client)

        session = session_service.create("test")
        events = list(chat.stream(session.id, "do it"))

        types_seq = [e.type for e in events]
        assert "tool_call" in types_seq, types_seq
        assert "tool_result" in types_seq, types_seq
        # 两轮 message_start（工具轮 + 文本轮）
        assert types_seq.count("message_start") == 2, types_seq
        assert types_seq[-1] == "done", types_seq

        msgs = message_service.list_messages(session.id)
        roles = [m.role for m in msgs]
        assert roles == ["user", "assistant", "tool", "assistant"], roles
        assert msgs[1].tool_calls and msgs[1].tool_calls[0].name == "fake_tool"
        assert msgs[2].content == "fake-result"
        assert msgs[3].content == "完成"
        print("[B] 工具轮 通过")


def main():
    test_text_turn()
    test_tool_turn()
    print("\n全部用例通过 ✅")


if __name__ == "__main__":
    main()
