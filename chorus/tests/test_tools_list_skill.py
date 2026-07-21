"""list_skill 工具断言：列出技能包内文件，无此技能返 Error。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.skill import SkillLoader
from chorus.tools.builtin import ListSkillTool
from chorus.tools.framework import ToolContext


def _write_skill(root: Path, dir_name: str, body: str) -> None:
    d = root / dir_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_list_skill_enumerates_files():
    tmp = Path(tempfile.mkdtemp())
    _write_skill(tmp, "alpha", "---\nname: a\ndescription: x\n---\nb")
    (tmp / "alpha" / "preview").mkdir()
    (tmp / "alpha" / "preview" / "desktop.html").write_text("h", encoding="utf-8")
    tool = ListSkillTool(SkillLoader(skills_dir=tmp))
    result = tool.run({"name": "a"}, ToolContext())
    content = result.outcome.content
    assert "SKILL.md" in content
    assert "preview/desktop.html" in content


def test_list_skill_unknown_returns_error():
    tmp = Path(tempfile.mkdtemp())
    tool = ListSkillTool(SkillLoader(skills_dir=tmp))
    result = tool.run({"name": "nope"}, ToolContext())
    assert result.outcome.content.startswith("Error:")


def main():
    test_list_skill_enumerates_files()
    test_list_skill_unknown_returns_error()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()