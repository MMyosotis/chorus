# chorus/tests/test_domain_activity.py
"""Activity 翻译层纯函数 smoke：started/tool_done/progress/visibility。

运行：``.venv/bin/python -m chorus.tests.test_domain_activity``
"""
from __future__ import annotations

from chorus.domain.task.activity import (
    ActivityDraft,
    done_activity,
    failed_activity,
    image_progress_preview,
    is_user_visible_tool,
    started_activity,
    tool_done_activity,
    tool_started_activity,
)


def test_started_activity_uses_profile_enter_line():
    d = started_activity("image")
    assert d.event_type == "started"
    assert d.status == "running"
    assert d.role_line  # 非空（取自 AGENT_PROFILES enter_line）


def test_is_user_visible_tool():
    assert is_user_visible_tool("baidu_search") is True
    assert is_user_visible_tool("generate_image") is True
    assert is_user_visible_tool("output_plan") is True
    assert is_user_visible_tool("load_skill") is False
    assert is_user_visible_tool("unknown") is False


def test_tool_started_activity_hidden_tool_returns_none():
    # load_skill 不可见 → None（不写 tool activity）
    assert tool_started_activity("idea", "load_skill", {}) is None


def test_tool_done_activity_baidu_search_summary():
    meta = {"refs": [{"title": "t1", "url": "u1", "snippet": "s1"},
                     {"title": "t2", "url": "u2", "snippet": "s2"}]}
    d = tool_done_activity("idea", "baidu_search", meta, None, [])
    assert d is not None
    assert d.summary_json["type"] == "search_results"
    assert d.summary_json["total"] == 2
    assert d.progress_json is None  # 搜索不写 progress


def test_tool_done_activity_generate_image_progress_with_metadata():
    meta = {"url": "https://img/2.jpg"}
    done = ["https://img/1.jpg"]  # 已有 1 张，本次第 2 张
    d = tool_done_activity("image", "generate_image", meta,
                           {"progress_total": 3, "progress_unit": "张图"}, done)
    assert d is not None
    # done_images 传入时尚未追加本次 url，progress current = len(done)+1 = 2
    assert d.progress_json["current"] == 2
    assert d.progress_json["total"] == 3
    assert d.artifact_preview_json["type"] == "images"
    assert len(d.artifact_preview_json["items"]) == 2  # 含本次


def test_tool_done_activity_generate_image_no_metadata_only_count():
    meta = {"url": "https://img/1.jpg"}
    d = tool_done_activity("image", "generate_image", meta, None, [])
    assert d is not None
    # 无 progress_total → 不显示 current/total，只显示已生成数量
    assert d.progress_json is None
    assert d.artifact_preview_json["type"] == "images"


def test_image_progress_preview():
    prog, preview = image_progress_preview(3, ["u1", "u2"])
    assert prog["current"] == 2 and prog["total"] == 3
    assert len(preview["items"]) == 2


def test_done_and_failed_activity():
    from chorus.domain.task import Narrative
    nar = Narrative(awaiting_line="等你", done_line="搞定")
    d = done_activity("idea", nar)
    assert d.event_type == "done" and d.status == "done"
    assert d.role_line == "搞定"
    f = failed_activity("idea", "boom")
    assert f.event_type == "failed" and f.status == "failed"
    assert "boom" in f.role_line or f.detail_md


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
