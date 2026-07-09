"""Markdown 产出解析:注释元信息抽取 + 四角色解析,纯函数。"""
from chorus.domain.task.markdown import (
    parse_meta, strip_markdown_meta, parse_script_md,
    parse_idea_md, parse_image_md, parse_postcard_md,
)


def test_parse_meta_extracts_awaiting_done():
    content = "<!-- chorus:awaiting=等你过目 -->\n<!-- chorus:done=写完了 -->\n\n正文"
    meta = parse_meta(content)
    assert meta == {"awaiting": "等你过目", "done": "写完了"}


def test_parse_meta_empty_when_no_comments():
    assert parse_meta("纯正文无注释") == {}


def test_parse_meta_skips_non_chorus_comments():
    content = "<!-- 普通注释 -->\n<!-- chorus:cover=图1 -->"
    assert parse_meta(content) == {"cover": "图1"}


def test_strip_markdown_meta_removes_comment_lines():
    content = "<!-- chorus:done=x -->\n## 标题\n正文"
    assert strip_markdown_meta(content) == "## 标题\n正文"


def test_strip_keeps_blank_structure():
    content = "<!-- chorus:done=x -->\n\n## 标题"
    assert strip_markdown_meta(content) == "\n## 标题"


def test_parse_script_md_heading_paragraph_list_quote():
    body = "## 阳台上的光\n\n阳台上的光，是慢慢挪过来的。\n\n- 粗陶杯\n- 粗砂糖\n\n> 秋天不是用来赶的。"
    blocks = parse_script_md(body)
    assert blocks == [
        {"kind": "heading", "text": "阳台上的光"},
        {"kind": "paragraph", "text": "阳台上的光，是慢慢挪过来的。"},
        {"kind": "list", "text": "粗陶杯\n粗砂糖"},
        {"kind": "quote", "text": "秋天不是用来赶的。"},
    ]


def test_parse_script_md_consecutive_paragraphs():
    body = "第一段。\n\n第二段。"
    blocks = parse_script_md(body)
    assert [b["kind"] for b in blocks] == ["paragraph", "paragraph"]
    assert blocks[0]["text"] == "第一段。"


def test_parse_script_md_empty_body():
    assert parse_script_md("") == []


def test_parse_idea_md_candidates():
    body = "### 阳台上的慢时光\n- 视角：物候\n- 理由：以光线挪动串起时间\n\n### 一杯仪式感\n- 视角：器物\n- 理由：器物即情绪"
    out = parse_idea_md(body)
    assert out["selected"] is None
    assert len(out["candidates"]) == 2
    assert out["candidates"][0] == {"index": 0, "title": "阳台上的慢时光", "angle": "物候", "reason": "以光线挪动串起时间"}
    assert out["candidates"][1]["index"] == 1


def test_parse_image_md_captions():
    body = "### 图 1\ncaption：阳台俯拍\n\n### 图 2\ncaption：侧拍暖光"
    out = parse_image_md(body)
    assert out["images"] == [{"url": "", "caption": "阳台俯拍"}, {"url": "", "caption": "侧拍暖光"}]


def test_parse_postcard_md_tree():
    body = ("# 秋日阳台\n\n## 关于这杯\n\n阳台上的光，慢慢挪过来。\n\n"
            "> 秋天不是用来赶的。\n\n![](图2)\n*俯拍*\n\n#标签：#秋日 #阳台")
    out = parse_postcard_md(body)
    assert out["title"] == "秋日阳台"
    assert out["tags"] == ["#秋日", "#阳台"]
    kinds = [s["kind"] for s in out["sections"]]
    assert "heading" in kinds and "quote" in kinds and "image" in kinds


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
