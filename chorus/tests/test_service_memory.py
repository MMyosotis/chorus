"""MemoryService 编排层断言：摘要、召回、提取、整理与人工确认三钩点。

用 FakeClient 模拟旁路 LLM，fresh_engine 临时库隔离。
"""
from __future__ import annotations

import json
import time
import types

from chorus.domain.memory import CreatorMemory
from chorus.domain.memory.service import MemoryLLMService
from chorus.domain.message import AssistantMessage, UserMessage
from chorus.domain.task import Task
from chorus.domain.task.artifacts import IdeaArtifacts, IdeaCandidate, PostCard
from chorus.repo.creator_memory import CreatorMemoryRepository
from chorus.repo.message import MessageRepository
from chorus.repo.settings import SettingsRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.services.memory import MemoryService
from chorus.services.settings import SettingsService
from chorus.tests._helpers import fresh_engine, seed_session


class FakeResponse:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(
            message=types.SimpleNamespace(content=content)
        )]


class FakeClient:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._scripts.pop(0)


class ErrorClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._raise))

    def _raise(self, **kwargs):
        raise Exception("LLM 不可用")


def _make_memory(**overrides):
    defaults = dict(
        id="m1", description="测试记忆", content="正文",
        platform=[], visible_to=[], kind="reference",
        created_at=0.0, updated_at=0.0,
    )
    defaults.update(overrides)
    return CreatorMemory(**defaults)


def _setup(client):
    engine = fresh_engine()
    seed_session(engine, "s1")
    memory_repo = CreatorMemoryRepository(engine)
    message_repo = MessageRepository(engine)
    art_repo = TaskArtifactsRepository(engine)
    task_repo = TaskRepository(engine)
    settings_svc = SettingsService(SettingsRepository(engine))
    llm_svc = MemoryLLMService(client, "fake")
    memory_svc = MemoryService(
        memory_repo, llm_svc, settings_svc, message_repo, art_repo,
    )
    return memory_repo, message_repo, art_repo, task_repo, settings_svc, memory_svc


def _seed_task(task_repo, task_id="t1", agent_type="idea"):
    task_repo.insert(Task(
        id=task_id, session_id="s1", pipeline_id="p1",
        agent_type=agent_type, status="finished",
        created_at=0.0, updated_at=0.0,
    ))


def test_build_digest_disabled_returns_empty():
    _, _, _, _, settings_svc, memory_svc = _setup(FakeClient([]))
    settings_svc.set_memory_enabled(False)
    digest = memory_svc.build_digest("supervisor")
    assert digest.is_empty


def test_build_digest_filters_by_visibility():
    memory_repo, _, _, _, _, memory_svc = _setup(FakeClient([]))
    memory_repo.upsert(_make_memory(id="m1", description="通用", visible_to=[]))
    memory_repo.upsert(_make_memory(id="m2", description="仅文案", visible_to=["script"]))
    supervisor_digest = memory_svc.build_digest("supervisor")
    assert len(supervisor_digest.entries) == 2
    idea_digest = memory_svc.build_digest("idea")
    assert len(idea_digest.entries) == 1
    assert idea_digest.entries[0].id == "m1"
    script_digest = memory_svc.build_digest("script")
    assert len(script_digest.entries) == 2


def test_recall_disabled_returns_empty():
    memory_repo, _, _, _, settings_svc, memory_svc = _setup(FakeClient([]))
    memory_repo.upsert(_make_memory(id="m1"))
    settings_svc.set_memory_enabled(False)
    result = memory_svc.recall("supervisor", "hint")
    assert result == []


def test_recall_returns_selected_memories():
    memory_repo, _, _, _, _, memory_svc = _setup(
        FakeClient([FakeResponse('["m1", "m3"]')])
    )
    for memory_id in ("m1", "m2", "m3"):
        memory_repo.upsert(_make_memory(id=memory_id, description=f"记忆{memory_id}"))
    result = memory_svc.recall("supervisor", "test hint")
    assert len(result) == 2
    assert {memory.id for memory in result} == {"m1", "m3"}


def test_recall_llm_failure_returns_empty():
    memory_repo, _, _, _, _, memory_svc = _setup(ErrorClient())
    memory_repo.upsert(_make_memory(id="m1"))
    result = memory_svc.recall("supervisor", "hint")
    assert result == []


def test_extract_upserts_drafts_and_skips_consolidate():
    memory_repo, message_repo, _, _, _, memory_svc = _setup(
        FakeClient([FakeResponse(json.dumps([
            {"description": "身份：程序员", "content": "用户是程序员",
             "platform": [], "visible_to": []},
            {"description": "文风：短句", "content": "偏好短句",
             "platform": ["小红书"], "visible_to": ["script"]},
        ]))])
    )
    message_repo.append(UserMessage(id="u1", session_id="s1", created_at=0.0, content="我是程序员"))
    message_repo.append(AssistantMessage(id="a1", session_id="s1", created_at=1.0, content="了解了"))
    memory_svc.extract("s1")
    memories = memory_repo.list_all()
    assert len(memories) == 2
    descs = {memory.description for memory in memories}
    assert "身份：程序员" in descs
    assert "文风：短句" in descs
    assert all(memory.kind == "reference" for memory in memories)


def test_extract_disabled_short_circuits():
    memory_repo, message_repo, _, _, settings_svc, memory_svc = _setup(FakeClient([]))
    settings_svc.set_memory_enabled(False)
    memory_svc.extract("s1")
    assert memory_repo.list_all() == []


def test_extract_llm_failure_preserves_store():
    memory_repo, message_repo, _, _, _, memory_svc = _setup(ErrorClient())
    memory_repo.upsert(_make_memory(id="m1", description="已有记忆"))
    message_repo.append(UserMessage(id="u1", session_id="s1", created_at=0.0, content="新对话"))
    memory_svc.extract("s1")
    memories = memory_repo.list_all()
    assert len(memories) == 1
    assert memories[0].id == "m1"


def test_consolidate_below_threshold_no_change():
    memory_repo, _, _, _, _, memory_svc = _setup(FakeClient([]))
    for i in range(5):
        memory_repo.upsert(_make_memory(id=f"m{i}", description=f"记忆{i}"))
    memory_svc.consolidate()
    memories = memory_repo.list_all()
    assert len(memories) == 5


def test_consolidate_at_threshold_replaces_all():
    memory_repo, _, _, _, _, memory_svc = _setup(
        FakeClient([FakeResponse(json.dumps([
            {"description": "合并后记忆A", "content": "内容A",
             "platform": [], "visible_to": [], "kind": "reference"},
            {"description": "合并后记忆B", "content": "内容B",
             "platform": [], "visible_to": [], "kind": "performance"},
        ]))])
    )
    for i in range(30):
        memory_repo.upsert(_make_memory(id=f"m{i}", description=f"记忆{i}"))
    memory_svc.consolidate()
    memories = memory_repo.list_all()
    assert len(memories) == 2
    descs = {memory.description for memory in memories}
    assert descs == {"合并后记忆A", "合并后记忆B"}


def test_consolidate_preserves_timestamp_from_llm():
    memory_repo, _, _, _, _, memory_svc = _setup(
        FakeClient([FakeResponse(json.dumps([
            {"description": "保留的", "content": "内容",
             "platform": [], "visible_to": [], "kind": "reference",
             "created_at": "2024-03-15 14:30"},
        ]))])
    )
    for i in range(30):
        memory_repo.upsert(_make_memory(id=f"m{i}", description=f"记忆{i}"))
    memory_svc.consolidate()
    memories = memory_repo.list_all()
    assert len(memories) == 1
    expected = time.mktime(time.strptime("2024-03-15 14:30", "%Y-%m-%d %H:%M"))
    assert memories[0].created_at == expected


def test_consolidate_empty_result_preserves_store():
    memory_repo, _, _, _, _, memory_svc = _setup(FakeClient([FakeResponse("不是 JSON")]))
    for i in range(30):
        memory_repo.upsert(_make_memory(id=f"m{i}", description=f"记忆{i}"))
    memory_svc.consolidate()
    assert len(memory_repo.list_all()) == 30


def test_consolidate_llm_failure_preserves_store():
    memory_repo, _, _, _, _, memory_svc = _setup(ErrorClient())
    for i in range(30):
        memory_repo.upsert(_make_memory(id=f"m{i}", description=f"记忆{i}"))
    memory_svc.consolidate()
    assert len(memory_repo.list_all()) == 30


def test_record_selection_upserts_reference_memory():
    memory_repo, _, art_repo, task_repo, _, memory_svc = _setup(FakeClient([]))
    _seed_task(task_repo, "t1", "idea")
    art_repo.upsert("t1", "idea", IdeaArtifacts(
        candidates=[IdeaCandidate(index=0, title="测试标题", angle="独特角度", reason="有共鸣")],
        selected=0,
    ))
    memory_svc.record_selection("t1", "idea")
    memories = memory_repo.list_all()
    assert len(memories) == 1
    memory = memories[0]
    assert "选题偏好" in memory.description
    assert "独特角度" in memory.description
    assert memory.kind == "reference"
    assert memory.visible_to == ["idea"]


def test_record_publication_upserts_reference_memory():
    memory_repo, _, art_repo, task_repo, _, memory_svc = _setup(FakeClient([]))
    _seed_task(task_repo, "t2", "finalize")
    art_repo.upsert("t2", "finalize", PostCard(markdown="这是发布的正文内容"))
    memory_svc.record_publication("t2", "finalize")
    memories = memory_repo.list_all()
    assert len(memories) == 1
    memory = memories[0]
    assert "已发布作品" in memory.description
    assert "这是发布的正文内容" in memory.content
    assert memory.kind == "reference"
    assert memory.visible_to == ["finalize"]


def test_record_correction_upserts_reference_memory():
    memory_repo, _, _, _, _, memory_svc = _setup(FakeClient([]))
    memory_svc.record_correction("t3", "finalize", "语气太正式，需要更口语化")
    memories = memory_repo.list_all()
    assert len(memories) == 1
    memory = memories[0]
    assert "改稿反馈" in memory.description
    assert "语气太正式" in memory.content
    assert memory.kind == "reference"
    assert memory.visible_to == ["finalize"]


def test_record_selection_disabled_short_circuits():
    memory_repo, _, _, _, settings_svc, memory_svc = _setup(FakeClient([]))
    settings_svc.set_memory_enabled(False)
    memory_svc.record_selection("t1", "idea")
    assert memory_repo.list_all() == []


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
