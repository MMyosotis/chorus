"""task_artifacts repo smoke + round-trip 测试。

四种角色产物模型存取往返等价；行自带角色，repo 自洽还原。
"""
from __future__ import annotations

from chorus.domain.task import (
    IdeaArtifacts,
    IdeaCandidate,
    ImageArtifacts,
    ImageItem,
    PostCard,
    ScriptArtifacts,
    Task,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.tests._helpers import fresh_engine, seed_session


def _setup():
    engine = fresh_engine()
    seed_session(engine)  # 须先建 sessions 父行（外键约束）
    TaskRepository(engine).insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", dependencies=[],
        created_at=0.0, updated_at=0.0,
    ))
    return engine


def test_artifacts_upsert_load():
    engine = _setup()
    repo = TaskArtifactsRepository(engine)
    assert repo.load("t1") is None
    repo.upsert(
        "t1", "idea",
        artifacts=IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="t", angle="a", reason="r")]),
    )
    got = repo.load("t1")
    assert got is not None
    assert isinstance(got.artifacts, IdeaArtifacts)
    assert got.artifacts.candidates[0].title == "t"
    # upsert 覆盖
    repo.upsert(
        "t1", "idea",
        artifacts=IdeaArtifacts(candidates=[IdeaCandidate(index=1, title="t2", angle="a", reason="r")]),
    )
    got2 = repo.load("t1")
    assert got2.artifacts.candidates[0].index == 1


def test_artifacts_load_many():
    engine = _setup()
    TaskRepository(engine).insert(Task(
        id="t2", session_id="s1", pipeline_id="p1", agent_type="script",
        status="pending", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(engine)
    repo.upsert(
        "t1", "idea",
        IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="t", angle="a", reason="r")]),
    )
    repo.upsert(
        "t2", "script",
        ScriptArtifacts(markdown="hi"),
    )
    many = repo.load_many(["t1", "t2", "t3"])
    assert set(many.keys()) == {"t1", "t2"}
    assert isinstance(many["t2"].artifacts, ScriptArtifacts)
    assert many["t2"].artifacts.markdown == "hi"


def test_roundtrip_idea():
    engine = _setup()
    repo = TaskArtifactsRepository(engine)
    idea = IdeaArtifacts(
        candidates=[IdeaCandidate(index=0, title="标题", angle="角度", reason="理由")],
        selected=0,
    )
    repo.upsert("t1", "idea", idea)
    got = repo.load("t1")
    assert got.artifacts == idea


def test_roundtrip_script():
    engine = _setup()
    TaskRepository(engine).insert(Task(
        id="ts", session_id="s1", pipeline_id="p1", agent_type="script",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(engine)
    script = ScriptArtifacts(markdown="# 标题\n\n正文")
    repo.upsert("ts", "script", script)
    got = repo.load("ts")
    assert got.artifacts == script


def test_roundtrip_image():
    engine = _setup()
    TaskRepository(engine).insert(Task(
        id="ti", session_id="s1", pipeline_id="p1", agent_type="image",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(engine)
    img = ImageArtifacts(images=[
        ImageItem(url="http://x/1.jpg", caption="图一"),
        ImageItem(url="http://x/2.jpg"),
    ])
    repo.upsert("ti", "image", img)
    got = repo.load("ti")
    assert got.artifacts == img


def test_roundtrip_postcard():
    engine = _setup()
    TaskRepository(engine).insert(Task(
        id="tf", session_id="s1", pipeline_id="p1", agent_type="finalize",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(engine)
    card = PostCard(
        markdown="# 夏日晚风\n\n一段正文\n\n![封](http://x/a.jpg)",
        meta={"preview_ref": "a/b", "stylesheet_ref": "a/c", "title": "夏日晚风"},
    )
    repo.upsert("tf", "finalize", card)
    got = repo.load("tf")
    assert got.artifacts == card


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
