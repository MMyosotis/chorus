"""Markdown 产出解析:四角色正文解析,纯函数。"""
from __future__ import annotations

import pytest

from chorus.domain.task.errors import ValidationError
from chorus.domain.task.markdown import (
    parse_script_md,
    parse_idea_md, parse_image_md, parse_postcard_md,
)
from chorus.domain.task.progress import UnitCounter


def test_parse_script_md_returns_markdown():
    body = "---\ntitle: 阳台上的光\n---\n\n阳台上的光，是慢慢挪过来的。\n\n- 粗陶杯\n- 粗砂糖\n\n> 秋天不是用来赶的。"
    out = parse_script_md(body)
    assert out["markdown"] == body


def test_parse_script_md_requires_front_matter_title_and_rejects_h1():
    """标题必须在 front matter，正文不能重复为一级标题。"""
    with pytest.raises(ValidationError):
        parse_script_md("## 小标题\n\n正文")
    with pytest.raises(ValidationError):
        parse_script_md("---\ntitle: 一\n---\n\n# 一\n\n正文")


def test_parse_script_md_empty_body_raises():
    """空正文直接抛错让模型自纠。"""
    with pytest.raises(ValidationError):
        parse_script_md("")


def test_parse_idea_md_candidates():
    body = "### 阳台上的慢时光\n- 视角：物候\n- 理由：以光线挪动串起时间\n\n### 一杯仪式感\n- 视角：器物\n- 理由：器物即情绪"
    out = parse_idea_md(body)
    assert out["selected"] is None
    assert len(out["candidates"]) == 2
    assert out["candidates"][0] == {"index": 0, "title": "阳台上的慢时光", "angle": "物候", "reason": "以光线挪动串起时间"}
    assert out["candidates"][1]["index"] == 1


def test_parse_image_md_captions():
    body = "![阳台俯拍](http://x/a.png)\n\n![侧拍暖光](http://x/b.png)"
    out = parse_image_md(body)
    assert out["images"] == [{"url": "http://x/a.png", "caption": "阳台俯拍"}, {"url": "http://x/b.png", "caption": "侧拍暖光"}]


def test_parse_image_md_all_empty_url_raises():
    """全部 url 为空抛错让模型自纠。"""
    with pytest.raises(ValidationError):
        parse_image_md("![阳台]()\n\n![侧拍]()")


def test_parse_image_md_empty_raises():
    """无图片抛错让模型自纠。"""
    with pytest.raises(ValidationError):
        parse_image_md("只有文字")


def test_parse_postcard_md_strips_refs_to_meta():
    """front matter 抽资源引用入 meta，标题保留在 front matter。"""
    body = ("---\n"
            "title: 秋日阳台\n"
            "preview_ref: web-blog/preview/desktop.html\n"
            "stylesheet_ref: web-blog/preview/desktop.css\n"
            "summary: 一句话摘要\n"
            "tags: [秋日, 阳台]\n"
            "---\n\n"
            "## 关于这杯\n\n阳台上的光。\n\n"
            "> 秋天不是用来赶的。\n\n![俯拍](http://x/2.png)")
    out = parse_postcard_md(body)
    assert out["meta"]["preview_ref"] == "web-blog/preview/desktop.html"
    assert out["meta"]["stylesheet_ref"] == "web-blog/preview/desktop.css"
    assert out["meta"]["title"] == "秋日阳台"
    assert "preview_ref" not in out["markdown"]
    assert "stylesheet_ref" not in out["markdown"]
    assert "summary: 一句话摘要" in out["markdown"]
    assert "tags: [秋日, 阳台]" in out["markdown"]
    assert "title: 秋日阳台" in out["markdown"]
    assert "![俯拍](http://x/2.png)" in out["markdown"]


def test_parse_postcard_md_image_with_alt():
    """![caption](url) 原样保留在 markdown 正文里。"""
    body = ("---\ntitle: t\npreview_ref: a/b\nstylesheet_ref: a/c\nsummary: s\ntags: [x]\n---\n\n"
            "![俯拍](http://x/3.png)")
    out = parse_postcard_md(body)
    assert out["meta"]["title"] == "t"
    assert "![俯拍](http://x/3.png)" in out["markdown"]


def test_parse_postcard_md_requires_refs():
    """front matter 缺资源引用字段抛校验错。"""
    body = "---\ntitle: 标题\nsummary: s\ntags: [x]\n---\n\n正文。"
    with pytest.raises(ValidationError):
        parse_postcard_md(body)


def test_parse_postcard_md_unclosed_front_matter_reports_boundary():
    """有头无尾报边界未闭合，不混同字段缺失。"""
    body = "---\ntitle: t\npreview_ref: a/b\nstylesheet_ref: a/c\nsummary: s\n\n正文。"
    with pytest.raises(ValidationError, match="未闭合"):
        parse_postcard_md(body)


def test_parse_postcard_md_requires_front_matter_title_and_rejects_h1():
    body = "---\npreview_ref: a/b\nstylesheet_ref: a/c\n---\n\n正文。"
    with pytest.raises(ValidationError):
        parse_postcard_md(body)
    body = "---\ntitle: 标题\npreview_ref: a/b\nstylesheet_ref: a/c\n---\n\n# 标题\n\n正文。"
    with pytest.raises(ValidationError):
        parse_postcard_md(body)


def test_unit_counter_counts_heading_lines():
    counter = UnitCounter("## ")
    counter.feed("## 第一段\n\n")
    counter.feed("正文\n\n## 第二段")
    assert counter.count == 2


def test_unit_counter_ignores_partial_marker():
    counter = UnitCounter("## ")
    counter.feed("#")  # 不完整
    counter.feed("# 标题")  # 拼成 ## 标题
    assert counter.count == 1


def test_unit_counter_resets_between_tasks():
    counter = UnitCounter("### ")
    counter.feed("### a\n### b\n")
    assert counter.count == 2


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
