"""创作者记忆仓储契约：CRUD 与全删重写。"""
from __future__ import annotations

from chorus.domain.memory import CreatorMemory
from chorus.repo.creator_memory import CreatorMemoryRepository
from chorus.tests._helpers import fresh_engine


def _make_memory(memory_id: str, **overrides) -> CreatorMemory:
    defaults = dict(
        id=memory_id,
        description=f"记忆 {memory_id}",
        content="正文内容",
        platform=[],
        visible_to=[],
        kind="reference",
        created_at=1000.0,
    )
    defaults.update(overrides)
    return CreatorMemory(**defaults)


def test_list_all_empty_initially():
    repo = CreatorMemoryRepository(fresh_engine())
    assert repo.list_all() == []


def test_upsert_and_get():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1", description="第一条"))
    got = repo.get("m1")
    assert got is not None
    assert got.description == "第一条"


def test_upsert_overwrites():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1", description="旧"))
    repo.upsert(_make_memory("m1", description="新"))
    assert repo.get("m1").description == "新"


def test_get_missing_returns_none():
    repo = CreatorMemoryRepository(fresh_engine())
    assert repo.get("nope") is None


def test_get_many():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1"))
    repo.upsert(_make_memory("m2"))
    repo.upsert(_make_memory("m3"))
    result = repo.get_many(["m1", "m3"])
    assert {m.id for m in result} == {"m1", "m3"}


def test_get_many_empty_ids():
    repo = CreatorMemoryRepository(fresh_engine())
    assert repo.get_many([]) == []


def test_delete():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1"))
    repo.delete("m1")
    assert repo.get("m1") is None


def test_replace_all_swaps_entire_set():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1"))
    repo.upsert(_make_memory("m2"))
    repo.replace_all([_make_memory("m3"), _make_memory("m4")])
    ids = {m.id for m in repo.list_all()}
    assert ids == {"m3", "m4"}


def test_replace_all_with_empty_clears_all():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1"))
    repo.replace_all([])
    assert repo.list_all() == []


def test_json_fields_round_trip():
    repo = CreatorMemoryRepository(fresh_engine())
    repo.upsert(_make_memory("m1", platform=["小红书"], visible_to=["script"]))
    got = repo.get("m1")
    assert got.platform == ["小红书"]
    assert got.visible_to == ["script"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
