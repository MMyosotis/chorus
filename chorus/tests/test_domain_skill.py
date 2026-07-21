"""Skill 领域纯逻辑断言：from_markdown / SkillLoader（扫描 + 摘要 + 提示段）。

覆盖 frontmatter 解析、缺 frontmatter 用兜底名、提示段拼装、扫描 SKILL.md 并按名缓存。
用临时目录，不碰项目 DB。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.skill import SkillContent, SkillLoader


def test_from_markdown_parses_frontmatter():
    text = "---\nname: my-skill\ndescription: 一个技能\n---\n\n正文内容"
    c = SkillContent.from_markdown(text, fallback_name="fallback")
    assert c.name == "my-skill"
    assert c.description == "一个技能"
    assert c.full_content == text  # 保留原文


def test_from_markdown_uses_fallback_when_no_frontmatter():
    text = "纯正文没有 frontmatter"
    c = SkillContent.from_markdown(text, fallback_name="fallback")
    assert c.name == "fallback"
    assert c.description == ""


def test_from_markdown_ignores_unknown_keys_has_no_tags_field():
    # 模型无 tags 字段，多余键被忽略
    text = "---\nname: x\ndescription: y\ntags: [a, b]\n---\nbody"
    c = SkillContent.from_markdown(text, fallback_name="fb")
    assert c.name == "x"
    assert c.description == "y"
    assert not hasattr(c, "tags")


def test_from_markdown_malformed_frontmatter_falls_back():
    # 只有开头无闭合，解析失败走兜底
    text = "---name: x\ndescription: y"
    c = SkillContent.from_markdown(text, fallback_name="fb")
    assert c.name == "fb"
    assert c.description == ""


def test_format_hints_empty_returns_empty_string():
    tmp = Path(tempfile.mkdtemp())
    loader = SkillLoader(skills_dir=tmp)
    assert loader.format_hints() == ""


def test_format_hints_renders_names_and_descriptions():
    tmp = Path(tempfile.mkdtemp())
    _write_skill(tmp, "infographic", "---\nname: infographic\ndescription: 做信息图\n---\nb")
    _write_skill(tmp, "writer", "---\nname: writer\ndescription: 写文案\n---\nb")
    loader = SkillLoader(skills_dir=tmp)
    out = loader.format_hints()
    assert "## 可用技能" in out
    assert "load_skill" in out
    assert "**infographic**: 做信息图" in out
    assert "**writer**: 写文案" in out


def _write_skill(root: Path, dir_name: str, body: str) -> Path:
    d = root / dir_name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "SKILL.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_skill_loader_scans_temp_dir_and_resolves_by_name():
    tmp = Path(tempfile.mkdtemp())
    _write_skill(tmp, "alpha", "---\nname: alpha-skill\ndescription: 阿尔法\n---\nbody-a")
    loader = SkillLoader(skills_dir=tmp)
    summaries = loader.list_summaries()
    assert [s.name for s in summaries] == ["alpha-skill"]
    assert summaries[0].description == "阿尔法"
    full = loader.get("alpha-skill")
    assert full is not None
    assert "body-a" in full.full_content
    assert loader.get("nope") is None


def test_skill_loader_fallback_name_is_parent_dir_name():
    tmp = Path(tempfile.mkdtemp())
    # 无 frontmatter，名字回退为目录名
    _write_skill(tmp, "dir-named", "纯正文")
    loader = SkillLoader(skills_dir=tmp)
    assert loader.get("dir-named") is not None
    assert loader.get("dir-named").description == ""


def test_skill_loader_ignores_non_skill_md_files():
    tmp = Path(tempfile.mkdtemp())
    _write_skill(tmp, "alpha", "---\nname: a\ndescription: x\n---\nb")
    # 非 SKILL.md 命名的文件应被忽略
    (tmp / "alpha" / "README.md").write_text("noise", encoding="utf-8")
    loader = SkillLoader(skills_dir=tmp)
    names = [s.name for s in loader.list_summaries()]
    assert names == ["a"]  # 只扫到 SKILL.md


def test_skill_loader_missing_dir_yields_empty():
    loader = SkillLoader(skills_dir=Path("/nonexistent-skill-dir-xyz"))
    assert loader.list_summaries() == []  # 不抛


def test_list_files_enumerates_package_files():
    tmp = Path(tempfile.mkdtemp())
    _write_skill(tmp, "alpha", "---\nname: a\ndescription: x\n---\nb")
    (tmp / "alpha" / "preview").mkdir()
    (tmp / "alpha" / "preview" / "desktop.html").write_text("h", encoding="utf-8")
    (tmp / "alpha" / "platform.yaml").write_text("y", encoding="utf-8")
    loader = SkillLoader(skills_dir=tmp)
    files = loader.list_files("a")
    assert files is not None
    assert "SKILL.md" in files
    assert "preview/desktop.html" in files
    assert "platform.yaml" in files
    assert loader.list_files("nope") is None


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
