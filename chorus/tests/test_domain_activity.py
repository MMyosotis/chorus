# chorus/tests/test_domain_activity.py
"""Activity 翻译层纯函数 smoke：started/tool_done/progress/visibility。

载荷收敛为单一具名 dataclass（SearchResultsPayload / ImageProgressPayload / FailedPayload），
由 ActivityDraft.payload 携带，event_type 区分多态。

运行：``.venv/bin/python -m chorus.tests.test_domain_activity``
"""
from __future__ import annotations

from chorus.domain.task.activity import (
    done_activity,
    failed_activity,
    image_progress,
    started_activity,
    tool_done_activity,
    tool_started_activity,
)
from chorus.domain.task.models import (
    FailedPayload,
    ImageProgressPayload,
    SearchResultsPayload,
)


def test_started_activity_uses_profile_enter_line():
    d = started_activity("image")
    assert d.event_type == "started"
    assert d.status == "running"
    assert d.role_line  # 非空（取自 AGENT_PROFILES enter_line）
    assert d.payload is None  # started 无载荷


def test_tool_started_activity_unknown_tool_uses_fallback_line():
    # 未注册台词的工具走兜底，仍写 tool_started 活动
    d = tool_started_activity("load_skill", {})
    assert d.event_type == "tool_started"
    assert d.tool_name == "load_skill"
    assert d.role_line  # 兜底文案非空


def test_tool_done_activity_baidu_search_payload():
    meta = {"refs": [{"title": "t1", "url": "u1", "snippet": "s1"},
                     {"title": "t2", "url": "u2", "snippet": "s2"}]}
    d = tool_done_activity("baidu_search", meta, None, [])
    assert d is not None
    assert d.tool_name == "baidu_search"
    assert isinstance(d.payload, SearchResultsPayload)
    assert d.payload.total == 2
    assert d.payload.bullets[0]["title"] == "t1"


def test_tool_done_activity_generate_image_progress_with_total():
    meta = {"url": "https://img/2.jpg"}
    done = ["https://img/1.jpg"]  # 已有 1 张，本次第 2 张
    d = tool_done_activity("generate_image", meta, 3, done)
    assert d is not None
    assert isinstance(d.payload, ImageProgressPayload)
    # done_images 传入时尚未追加本次 url，但翻译器内部合并本次 → current = 2
    assert d.payload.current == 2
    assert d.payload.total == 3
    assert len(d.payload.items) == 2  # 含本次
    assert d.payload.unit == "张图"


def test_tool_done_activity_generate_image_no_total():
    meta = {"url": "https://img/1.jpg"}
    d = tool_done_activity("generate_image", meta, None, [])
    assert d is not None
    assert isinstance(d.payload, ImageProgressPayload)
    # 无 progress_total → total 为 None
    assert d.payload.total is None
    assert d.payload.current == 1
    assert len(d.payload.items) == 1


def test_image_progress():
    current, total = image_progress(3, ["u1", "u2"])
    assert current == 2 and total == 3
    # total 未知返 None
    current, total = image_progress(None, ["u1"])
    assert current == 1 and total is None


def test_done_and_failed_activity():
    from chorus.domain.task import Narrative
    nar = Narrative(awaiting_line="等你", done_line="搞定")
    d = done_activity(nar)
    assert d.event_type == "done" and d.status == "done"
    assert d.role_line == "搞定"
    assert d.payload is None  # done 无载荷
    f = failed_activity("boom")
    assert f.event_type == "failed" and f.status == "failed"
    assert isinstance(f.payload, FailedPayload)
    assert f.payload.detail_md == "boom"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
