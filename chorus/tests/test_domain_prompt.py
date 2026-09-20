"""提示词纯函数断言：supervisor / subagent 基础文案、条件段装配与首轮调用消息。

锚定 prompt 含关键锚点（create_plan 工具、profiles 注入、Markdown 产出协议、禁 emoji），
验证段顺序、缺料整段缺席与技能段 gating。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from chorus.domain.intent import Intent
from chorus.domain.memory import MemoryDigest
from chorus.domain.memory.models import CreatorMemory, MemoryDigestEntry
from chorus.domain.prompt import (
    InvokeInputs,
    SkeletonInputs,
    SubagentSystemInputs,
    SubagentUserInputs,
    SupervisorSystemInputs,
    subagent_base,
)
from chorus.domain.skill import SkillLoader
from chorus.domain.task import PostCard


_empty_loader = SkillLoader(skills_dir=Path("/nonexistent-skills"))
_empty_digest = MemoryDigest()


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
    p = SupervisorSystemInputs(digest=_empty_digest).render_system_prompt()
    assert "create_plan" in p
    assert "finalize" in p
    assert "选题官" in p


def test_subagent_system_prompt_includes_skill_and_digest():
    tmp = Path(tempfile.mkdtemp())
    skill_dir = tmp / "infographic"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: infographic\ndescription: 信息图配图法\n---\n正文",
        encoding="utf-8",
    )
    prompt = SubagentSystemInputs(
        agent_type="image", skill_hints=SkillLoader(skills_dir=tmp).format_hints(), digest=_empty_digest,
    ).render_system_prompt()
    assert "<available_skills>" in prompt
    assert "infographic" in prompt
    assert prompt.count("<available_skills>") == 1


def test_image_prompt_caps_retry():
    """配图 prompt 软约束：按张数生成、每张一次、服务故障不反复重试、回填 url、核对后收尾、相同 url 不误判、真失败走失败块。"""
    p = subagent_base("image")
    assert "按意图要求的张数生成" in p
    assert "每张只调用一次" in p
    assert "全部生成后核对张数再收尾" in p
    assert "字面含 Error 时才视为失败" in p
    assert "不要因为多张图返回相同 url 就判定为故障" in p
    assert "按产出协议写失败块" in p
    assert "![图注](图片url)" in p


def test_subagent_prompt_has_abandon_exit():
    """产出协议给所有角色留失败出口：# 失败 + 一句说明。"""
    for role in ("idea", "script", "image", "finalize"):
        p = subagent_base(role)
        assert "# 失败" in p
        assert "失败块" in p


def test_postcard_prompt_guides_image_url():
    """排版 prompt 指引：图片用 ![图注](url)，url 从上游配图取。"""
    p = subagent_base("finalize")
    assert "![图注](url)" in p
    assert "从上游配图产物取" in p


def test_memory_block_absent_without_digest():
    p = SupervisorSystemInputs(digest=_empty_digest).render_system_prompt()
    assert "<memory_summary>" not in p


def test_memory_block_present_with_digest():
    entry = MemoryDigestEntry(id="m1", description="身份：程序员", platform=["小红书"], kind="performance")
    digest = MemoryDigest(entries=[entry])
    p = SupervisorSystemInputs(digest=digest).render_system_prompt()
    assert "<memory_summary>" in p
    assert "身份：程序员" in p
    assert "小红书" in p


def test_inject_user_blocks_repeat_not_accumulate():
    """多轮注入不累积、不动调用方持有的字典：跨轮复用历史时标签只出现一次。"""
    memory = CreatorMemory(
        id="m1", description="身份", content="正文",
        platform=[], visible_to=[], kind="reference", created_at=0.0,
    )
    history = [{"role": "user", "content": "原始指令"}]
    for _ in range(3):
        msgs = [{"role": "system", "content": "系统"}] + history
        SubagentUserInputs(memories=[memory]).inject_user_context(msgs)
        assert msgs[1]["content"].count("<recalled_memories>") == 1
    assert history[0]["content"] == "原始指令"


def test_render_skeleton_note_and_base_card():
    """交待与底稿在建图时冻进骨架，缺省区块整段不出现。"""
    base_card = PostCard(markdown="---\ntitle: 夏日晚风\n---\n\n旧稿正文", meta={"title": "夏日晚风"})
    intent = Intent(topic="夏日晚风", image_count=1)
    skeleton = SkeletonInputs("idea", "标题整体保留，只微调语气", intent, base_card).render_skeleton()
    assert "<role>\n选题官\n</role>" in skeleton
    assert "<step_note>\n标题整体保留，只微调语气\n</step_note>" in skeleton
    assert "<base_card>" in skeleton
    assert "旧稿正文" in skeleton
    # 无交待：区块不出现，但底稿与意图仍在
    no_note = SkeletonInputs("finalize", "", intent, base_card).render_skeleton()
    assert "本步交待" not in no_note
    assert "<base_card>" in no_note
    # 无底稿：底稿区块整段不出现
    fresh = SkeletonInputs("idea", "", Intent(topic="新篇", image_count=1), None).render_skeleton()
    assert "<base_card>" not in fresh


def test_assemble_invoke_appends_sections_in_fixed_order():
    out = InvokeInputs(
        skeleton="骨架",
        dependencies=[("文案官", "旧稿正文")],
        prior="上轮正文",
        feedback="改标题",
    ).assemble_invoke()
    assert out.index("骨架") < out.index("<dependency_artifacts>") < out.index("<prior_artifact>") < out.index("<user_feedback>")
    assert "[文案官]\n旧稿正文" in out


def test_assemble_invoke_empty_sections_omitted():
    # 缺料整段缺席；全空时只剩骨架
    out = InvokeInputs(skeleton="骨架", dependencies=[]).assemble_invoke()
    assert out == "骨架"
    full = InvokeInputs(
        skeleton="骨架", dependencies=[("文案官", "正文")], feedback="改标题",
    ).assemble_invoke()
    assert "<prior_artifact>" not in full
    assert "<dependency_artifacts>" in full and "<user_feedback>" in full


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
