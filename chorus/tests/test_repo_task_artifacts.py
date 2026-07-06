"""task_artifacts repo smoke + round-trip 测试。

四种角色产物模型存取往返等价；行自带角色，repo 自洽还原。
"""
from __future__ import annotations

from chorus.domain.task import (
    IdeaArtifacts,
    IdeaCandidate,
    ImageArtifacts,
    ImageItem,
    Narrative,
    PostCard,
    PostImage,
    PostSection,
    ScriptArtifacts,
    ScriptBlock,
    Task,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.tests._helpers import fresh_conn, seed_session


def _setup():
    conn = fresh_conn()
    seed_session(conn)  # 须先建 sessions 父行（外键约束）
    TaskRepository(conn).insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="running", dependencies=[],
        created_at=0.0, updated_at=0.0,
    ))
    return conn


def test_artifacts_upsert_load():
    conn = _setup()
    repo = TaskArtifactsRepository(conn)
    assert repo.load("t1") is None
    repo.upsert(
        "t1", "idea",
        artifacts=IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="t", angle="a", reason="r")]),
        narrative=Narrative(awaiting_line="y", done_line="ok"),
    )
    got = repo.load("t1")
    assert got is not None
    assert isinstance(got.artifacts, IdeaArtifacts)
    assert got.artifacts.candidates[0].title == "t"
    assert got.narrative.done_line == "ok"
    # upsert 覆盖
    repo.upsert(
        "t1", "idea",
        artifacts=IdeaArtifacts(candidates=[IdeaCandidate(index=1, title="t2", angle="a", reason="r")]),
        narrative=Narrative(awaiting_line="y", done_line="new"),
    )
    got2 = repo.load("t1")
    assert got2.artifacts.candidates[0].index == 1
    assert got2.narrative.done_line == "new"


def test_artifacts_load_many():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="t2", session_id="s1", pipeline_id="p1", agent_type="script",
        status="pending", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    repo.upsert(
        "t1", "idea",
        IdeaArtifacts(candidates=[IdeaCandidate(index=0, title="t", angle="a", reason="r")]),
        Narrative(awaiting_line="y", done_line="x"),
    )
    repo.upsert(
        "t2", "script",
        ScriptArtifacts(blocks=[ScriptBlock(kind="paragraph", text="hi")]),
        Narrative(awaiting_line="y", done_line="y"),
    )
    many = repo.load_many(["t1", "t2", "t3"])
    assert set(many.keys()) == {"t1", "t2"}
    assert isinstance(many["t2"].artifacts, ScriptArtifacts)
    assert many["t2"].artifacts.blocks[0].text == "hi"


def test_roundtrip_idea():
    conn = _setup()
    repo = TaskArtifactsRepository(conn)
    idea = IdeaArtifacts(
        candidates=[IdeaCandidate(index=0, title="标题", angle="角度", reason="理由")],
        selected=0,
    )
    repo.upsert("t1", "idea", idea, Narrative(awaiting_line="待确认", done_line="完成"))
    got = repo.load("t1")
    assert got.artifacts == idea
    assert got.narrative == Narrative(awaiting_line="待确认", done_line="完成")


def test_roundtrip_script():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="ts", session_id="s1", pipeline_id="p1", agent_type="script",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    script = ScriptArtifacts(blocks=[
        ScriptBlock(kind="heading", text="标题"),
        ScriptBlock(kind="paragraph", text="正文"),
    ])
    repo.upsert("ts", "script", script, Narrative(awaiting_line="y", done_line="d"))
    got = repo.load("ts")
    assert got.artifacts == script


def test_roundtrip_image():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="ti", session_id="s1", pipeline_id="p1", agent_type="image",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    img = ImageArtifacts(images=[
        ImageItem(url="http://x/1.jpg", caption="图一"),
        ImageItem(url="http://x/2.jpg"),
    ])
    repo.upsert("ti", "image", img, Narrative(awaiting_line="y", done_line="d"))
    got = repo.load("ti")
    assert got.artifacts == img


def test_roundtrip_postcard():
    conn = _setup()
    TaskRepository(conn).insert(Task(
        id="tf", session_id="s1", pipeline_id="p1", agent_type="finalize",
        status="finished", dependencies=["t1"],
        created_at=0.0, updated_at=0.0,
    ))
    repo = TaskArtifactsRepository(conn)
    card = PostCard(
        title="夏日晚风",
        sections=[
            PostSection(kind="heading", text="一"),
            PostSection(kind="image", image=PostImage(url="http://x/a.jpg", caption="封")),
            PostSection(kind="list", text="- 项"),
        ],
        cover=PostImage(url="http://x/cover.jpg"),
        tags=["#夏", "#晚风"],
        summary="摘要",
    )
    repo.upsert("tf", "finalize", card, Narrative(awaiting_line="y", done_line="d"))
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
