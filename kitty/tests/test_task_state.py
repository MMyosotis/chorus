# kitty/tests/test_task_state.py
"""任务图纯函数表驱动断言：状态机 / pipeline / PostCard。

不碰 DB，成本极低。运行：`.venv/bin/python -m kitty.tests.test_task_state`
"""
from __future__ import annotations

# 用例在 Task 6（state_machine 完成）后填充。

from kitty.domain.task import PostCard, PostImage, PostSection


def test_postcard_contract():
    # 合法 PostCard：含 image section
    card = PostCard(
        title="夏日晚风",
        cover=PostImage(url="http://x/a.jpg"),
        sections=[
            PostSection(kind="heading", text="开篇"),
            PostSection(kind="paragraph", text="一段文字"),
            PostSection(kind="image", image=PostImage(url="http://x/b.jpg", caption="图注")),
            PostSection(kind="list", text="点一\n点二"),
        ],
        tags=["#夏天", "#随笔"],
        summary="一句摘要",
    )
    assert card.sections[2].image.url == "http://x/b.jpg"
    assert card.tags == ["#夏天", "#随笔"]


def test_postcard_rejects_unknown_kind():
    import pytest
    from pydantic import ValidationError as PydValidationError
    with pytest.raises(PydValidationError):
        PostSection(kind="table", text="x")  # type: ignore[arg-type]
