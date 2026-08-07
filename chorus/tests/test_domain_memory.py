"""创作者记忆领域纯函数断言：可见性判定、摘要判空与 prompt 构造。"""
from __future__ import annotations

from chorus.domain.memory import (
    CreatorMemory,
    MemoryDigest,
    render_digest_block,
    render_recall_block,
    visible_to_agent,
)
from chorus.domain.memory.models import MemoryDigestEntry
from chorus.domain.memory.prompts import (
    build_consolidate_prompt,
    build_extract_prompt,
    build_recall_prompt,
)
from chorus.domain.message import AssistantMessage, ToolMessage, UserMessage


def _make_memory(**overrides) -> CreatorMemory:
    defaults = dict(
        id="m1",
        description="测试记忆",
        content="正文",
        platform=[],
        visible_to=[],
        kind="reference",
        created_at=0.0,
        updated_at=0.0,
    )
    defaults.update(overrides)
    return CreatorMemory(**defaults)


def test_supervisor_always_visible():
    memory = _make_memory(visible_to=["script"])
    assert visible_to_agent(memory, "supervisor") is True


def test_empty_visible_to_means_all_agents():
    memory = _make_memory(visible_to=[])
    assert visible_to_agent(memory, "idea") is True
    assert visible_to_agent(memory, "script") is True
    assert visible_to_agent(memory, "finalize") is True


def test_listed_agent_visible():
    memory = _make_memory(visible_to=["script", "finalize"])
    assert visible_to_agent(memory, "script") is True
    assert visible_to_agent(memory, "finalize") is True


def test_unlisted_agent_not_visible():
    memory = _make_memory(visible_to=["script"])
    assert visible_to_agent(memory, "idea") is False
    assert visible_to_agent(memory, "image") is False


def test_digest_empty():
    digest = MemoryDigest(entries=[])
    assert digest.is_empty is True


def test_digest_non_empty():
    entry = MemoryDigestEntry(
        id="m1", description="测试", platform=["小红书"], kind="performance"
    )
    digest = MemoryDigest(entries=[entry])
    assert digest.is_empty is False


def test_recall_prompt_contains_task_hint_and_catalog():
    entries = [
        MemoryDigestEntry(id="m1", description="身份：程序员", platform=[], kind="performance"),
        MemoryDigestEntry(id="m2", description="文风：短句", platform=["小红书"], kind="reference"),
    ]
    digest = MemoryDigest(entries=entries)
    prompt = build_recall_prompt(digest, "写一篇关于 AI 的小红书帖子")
    assert "写一篇关于 AI 的小红书帖子" in prompt
    assert "m1" in prompt
    assert "m2" in prompt
    assert "身份：程序员" in prompt
    assert "小红书" in prompt


def test_extract_prompt_contains_reference_guide_and_history():
    history = [
        UserMessage(id="u1", session_id="s1", created_at=0.0, content="我是深圳的程序员"),
        AssistantMessage(id="a1", session_id="s1", created_at=1.0, content="了解了"),
        ToolMessage(id="t1", session_id="s1", created_at=2.0, tool_call_id="c1", name="baidu_search", content="搜索结果"),
    ]
    existing = [_make_memory(description="已有：城市深圳")]
    prompt = build_extract_prompt(history, existing)
    assert "深圳的程序员" in prompt
    assert "reference" in prompt
    assert "visible_to" in prompt
    assert "已有：城市深圳" in prompt


def test_consolidate_prompt_contains_threshold_and_promotion():
    memories = [
        _make_memory(id="m1", description="记忆一", content="内容一"),
        _make_memory(id="m2", description="记忆二", content="内容二"),
    ]
    prompt = build_consolidate_prompt(memories)
    assert "20" in prompt
    assert "performance" in prompt
    assert "晋升" in prompt
    assert "时间" in prompt
    assert "created_at" in prompt
    assert "记忆一" in prompt
    assert "内容一" in prompt
    assert "记忆二" in prompt


def test_render_digest_block_empty():
    assert render_digest_block(MemoryDigest(entries=[])) == ""


def test_render_digest_block_lists_entries():
    entries = [
        MemoryDigestEntry(id="m1", description="身份：程序员", platform=["小红书"], kind="performance"),
        MemoryDigestEntry(id="m2", description="文风：短句", platform=[], kind="reference"),
    ]
    block = render_digest_block(MemoryDigest(entries=entries))
    assert "## 创作者档案" in block
    assert "身份：程序员" in block
    assert "小红书" in block
    assert "已验证" in block
    assert "文风：短句" in block
    assert "参考" in block


def test_render_recall_block_empty():
    assert render_recall_block([]) == ""


def test_render_recall_block_wraps_memories():
    memories = [
        _make_memory(description="身份：程序员", content="深圳后端"),
        _make_memory(description="文风：短句", content="多短句少长句"),
    ]
    block = render_recall_block(memories)
    assert block.startswith("<recalled_memories>")
    assert block.endswith("</recalled_memories>")
    assert "身份：程序员" in block
    assert "深圳后端" in block
    assert "文风：短句" in block
    assert "多短句少长句" in block


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
