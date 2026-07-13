"""系统提示词纯函数断言：supervisor / subagent prompt 拼装规则与技能段 gating。

锚定 prompt 含关键锚点（create_plan 工具、profiles 注入、Markdown 产出协议与 chorus 注释话术、禁 emoji），
并验证技能段只在白名单含 load_skill 时拼入。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.prompt import (
    SYSTEM_PROMPT,
    PromptContext,
    build_system_prompt,
    subagent_base,
)
from chorus.domain.skill import SkillLoader


def test_subagent_prompts():
    for at in ("idea", "script", "image", "finalize"):
        p = subagent_base(at)
        assert "<!-- chorus:awaiting=" in p
        assert "<!-- chorus:done=" in p
        assert "<<<ARTIFACTS" not in p
        assert "禁用任何 emoji" in p


def test_supervisor_prompt_has_profiles():
    p = build_system_prompt(PromptContext(base=SYSTEM_PROMPT))
    assert "create_plan" in p
    assert "finalize" in p
    assert "选题官" in p


def test_skill_section_absent_without_load_skill():
    loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
    p = build_system_prompt(PromptContext(
        base=SYSTEM_PROMPT, tool_names=("update_intent_state",), skill_loader=loader,
    ))
    assert "可用技能" not in p


def test_skill_section_present_with_load_skill():
    tmp = Path(tempfile.mkdtemp())
    skill_dir = tmp / "infographic"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: infographic\ndescription: 信息图配图法\n---\n正文",
        encoding="utf-8",
    )
    loader = SkillLoader(skills_dir=tmp)
    p = build_system_prompt(PromptContext(
        base=SYSTEM_PROMPT, tool_names=("generate_image", "load_skill"), skill_loader=loader,
    ))
    assert "可用技能" in p
    assert "infographic" in p
    # 标题只出现一次（不与 format_hints 自带标题重复）
    assert p.count("可用技能") == 1


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
