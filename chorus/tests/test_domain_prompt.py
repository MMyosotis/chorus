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
        assert "话术注释" not in p
        assert "<<<ARTIFACTS" not in p
        assert "禁用任何 emoji" in p


def test_subagent_prompt_has_skill_fallback():
    """无匹配 Skill 时回退 web-blog，给模型确定路径而非撞墙。"""
    for at in ("idea", "script", "image", "finalize"):
        p = subagent_base(at)
        assert "没有与 platform 匹配的 Skill" in p
        assert "按 web-blog 技能的规格回退" in p


def test_subagent_prompt_guides_list_before_load():
    """引用资源前先 list_skill 看包内文件，不要凭空推测路径。"""
    for at in ("idea", "script", "image", "finalize"):
        p = subagent_base(at)
        assert "list_skill" in p
        assert "只能从 list_skill 的清单中挑" in p


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


def test_image_prompt_caps_retry():
    """配图 prompt 软约束：按张数生成、每张一次、服务故障不反复重试、回填 url、核对后收尾、相同 url 不误判、真失败走失败块。"""
    p = subagent_base("image")
    assert "按意图要求的张数生成" in p
    assert "每张只调用一次" in p
    assert "全部生成后核对张数再收尾" in p
    assert "字面含 Error 时才视为失败" in p
    assert "不要因为多张图返回相同 url 就判定为故障" in p
    assert "按产出协议写失败块" in p
    assert "### 图 1\nurl：图片url" in p


def test_subagent_prompt_has_abandon_exit():
    """产出协议给所有角色留失败出口：# 失败 + 一句说明。"""
    for role in ("idea", "script", "image", "finalize"):
        p = subagent_base(role)
        assert "# 失败" in p
        assert "失败块" in p


def test_postcard_prompt_guides_image_url():
    """汇总 prompt 指引：图片用 ![图注](url)，url 从上游配图取。"""
    p = subagent_base("finalize")
    assert "![图注](url)" in p
    assert "从上游配图产物取" in p


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
