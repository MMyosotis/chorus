"""子 agent 提示词：基础文案、每轮系统/用户段组装、首轮调用消息与纠错消息组装。

首轮调用消息固定段顺序：骨架（角色/交待/意图/底稿）→前置产物→上轮产物→用户反馈，
与基础文案声明的输入顺序一致；建图时只冻骨架，其余三段开跑时补齐。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from chorus.domain.intent import Intent
from chorus.domain.memory import (
    CreatorMemory,
    MemoryDigest,
    render_digest_block,
    render_recall_block,
)
from chorus.domain.prompt.assembly import (
    build_system_prompt,
    inject_user_blocks,
    join_sections,
    section,
)
from chorus.domain.skill import SkillLoader
from chorus.domain.task.artifacts import PostCard
from chorus.domain.task.models import TaskContent
from chorus.domain.task.profiles import AGENT_PROFILES

if TYPE_CHECKING:
    from chorus.domain.task.pipeline import StepSpec, TaskPlan

_BASE = (
    "你是多平台图文创作团队的{role_name}。{role_desc}\n\n"
    "禁用任何 emoji 字符，最终产物一律使用纯文本。\n\n"
    "## 你的输入\n"
    "首轮调用消息按固定顺序给出你的角色、本步交待（如有）、创作意图、底稿（如有）、"
    "前置产物、上轮产物与用户反馈。只做你的角色职责，复用上游已完成的内容，不要重做。"
    "前置产物若含多个候选，以 selected 指向的候选为准，不要自行换角度或混用其他候选。\n\n"
    "## 平台 Skill\n"
    "根据创作意图的 platform，在可用技能中选择与平台匹配的 Skill。"
    "先用 list_skill 列出该 Skill 包内有哪些文件，再用 load_skill 读取 SKILL.md 与本角色需要的参考文件。"
    "preview/stylesheet 等资源路径只能从 list_skill 的清单中挑，不要凭空推测路径。"
    "不要加载与当前平台无关的 Skill。平台规则决定内容风格，"
    "下方产出协议决定最终结构，两者都必须遵守。"
    "若可用技能中没有与 platform 匹配的 Skill，按 web-blog 技能的规格回退："
    "内容风格仍贴近原 platform，但结构、配图规格、资源引用一律套用 web-blog。\n\n"
    "## 产出协议\n"
    "完成创作后，在最后一轮（不再调用工具时）按以下 Markdown 格式输出产物正文：\n\n"
    "{artifacts_shape}\n\n"
    "若本步确实无法完成（如工具持续返回 Error 且换写法仍无效），不要写降级或残缺产物，"
    "直接输出失败块：第一行写 `# 失败`，换行后用一句话说明失败原因，"
    "系统据此标记本步失败并展示给用户，不要在此之外再写任何内容。\n\n"
    "{role_rules}\n"
    "只输出一份完整产物，不要加开场白、说明或收尾话。"
    "不要输出 JSON，不要用代码块包裹。"
    "如收到格式修正提示，重新输出修正后的完整产物。"
)

_SHAPES = {
    "idea": (
        "### <候选标题文字>\n"
        "- 视角：实际切入角度\n"
        "- 理由：实际推荐理由"
    ),
    "script": (
        "---\n"
        "title: 文章标题\n"
        "---\n\n"
        "## 小节\n\n段落正文。\n\n- 要点1\n- 要点2\n\n> 引文"
    ),
    "image": (
        "![图注](图片url)"
    ),
    "postcard": (
        "---\n"
        "title: 博文标题\n"
        "preview_ref: 已加载技能名/包内预览路径\n"
        "stylesheet_ref: 已加载技能名/包内样式路径\n"
        "summary: 一句话博文摘要\n"
        "tags: [话题1, 话题2]\n"
        "---\n\n"
        "## 小节\n\n段落。\n\n> 引文\n\n![图注](图url)"
    ),
}

_ROLE_RULES = {
    "idea": (
        "每个候选严格输出一组「### 标题 + 两项无序列表」，候选数量遵循平台 Skill。"
        "### 后面直接写真实的候选标题文字，不要写「真实标题」「候选标题」这类占位词。"
        "列表项只能是「视角：」和「理由：」，不加序号、导语或总结。"
    ),
    "script": (
        "产出以 YAML front matter 开头，其中必须有且仅有一个非空 title 字段。"
        "正文不要使用 # 大标题；其余可用 ## 小标题、普通段落、单层 - 无序列表、单段 > 引用与图片。"
        "不使用有序或嵌套列表，不同结构块之间空一行。"
        "若创作意图侧重配图，正文改为精简串场文案：每张图配一小段引导文字即可，不铺长文。"
    ),
    "image": (
        "调用 generate_image 生成配图，每张用 ![图注](url) 写出。"
        "把 generate_image 返回的 url 原样填进括号，不要凭空编造、不要替换、不要因为多张图返回相同 url 就判定为故障。"
        "按意图要求的张数生成，每张只调用一次；全部生成后核对张数再收尾。"
        "只有当工具返回内容字面含 Error 时才视为失败：换 1 种写法再试一次，"
        "仍失败就按产出协议写失败块，不要写空 url 的降级图。"
    ),
    "postcard": (
        "你是唯一成品出口：把 idea、script 和 image 产物装配为成品 markdown，"
        "不另起主题、不改写事实、不扩写正文；具体取舍与排列遵循平台 Skill。"
        "产出以 YAML front matter 开头，依次含 title、preview_ref、stylesheet_ref、summary、tags 五个字段。"
        "preview_ref 与 stylesheet_ref 引用已加载平台 Skill 给出的精确资源路径，格式为「技能名/包内路径」，不要自行改写。"
        "summary 写一句话博文摘要，tags 写话题标签数组。"
        "标题只能写在 front matter 的 title 字段；front matter 后是正文，不要使用 # 大标题，其余可用 ## 小标题、段落、单层 - 无序列表、单段 > 引用与图片。"
        "图片用 ![图注](url)，url 从上游配图产物取，不要凭空编造。"
        "不同结构块之间空一行。"
    ),
}


def subagent_base(agent_type: str) -> str:
    """按角色返回 system 基础文案。"""
    profile = AGENT_PROFILES[agent_type]
    return _BASE.format(
        role_name=profile.display_name,
        role_desc=profile.role_desc,
        artifacts_shape=_SHAPES[profile.artifacts_schema],
        role_rules=_ROLE_RULES[profile.artifacts_schema],
    )


@dataclass(frozen=True)
class SubagentSystemInputs:
    """子 agent 系统消息原料：角色、技能加载器与创作者档案摘要。"""

    agent_type: str
    skill_loader: SkillLoader
    digest: MemoryDigest

    def render_system_prompt(self) -> str:
        """拼接子 agent 的 system 消息。"""
        return build_system_prompt(subagent_base(self.agent_type), [
            self.skill_loader.format_hints(),
            render_digest_block(self.digest),
        ])


@dataclass(frozen=True)
class SubagentUserInputs:
    """子 agent 用户消息原料：当前召回的记忆。"""

    memories: list[CreatorMemory] = field(default_factory=list)

    def inject_user_context(self, msgs: list[dict]) -> None:
        """把子 agent 的用户上下文注入末条用户消息前。"""
        inject_user_blocks(msgs, [render_recall_block(self.memories)])


@dataclass(frozen=True)
class SkeletonInputs:
    """建图时冻进内容行的骨架原料：角色、交待、意图、底稿。"""

    agent_type: str
    note: str
    intent: Intent
    base_card: Optional[PostCard] = None

    @classmethod
    def from_plan(cls, plan: "TaskPlan", step: "StepSpec") -> "SkeletonInputs":
        """按任务计划与步骤生成骨架原料。"""
        return cls(
            agent_type=step.agent_type,
            note=step.note,
            intent=plan.intent,
            base_card=plan.base_card,
        )

    def render_skeleton(self) -> str:
        """建图时渲染并冻结骨架内容。"""
        intent_text = json.dumps(
            self.intent.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        sections = [
            f"角色：{AGENT_PROFILES[self.agent_type].display_name}",
            f"本步交待：{self.note}" if self.note else "",
            f"创作意图：\n{intent_text}",
            f"底稿：\n{self.base_card.markdown}" if self.base_card is not None else "",
        ]
        return "\n\n".join(section for section in sections if section)


def build_task_content(task_id: str, skeleton: SkeletonInputs) -> TaskContent:
    """按骨架渲染落库内容行。"""
    return TaskContent(task_id=task_id, invoke_message=skeleton.render_skeleton())


@dataclass(frozen=True)
class InvokeInputs:
    """首轮调用消息原料：骨架、前置产物、上轮产物与用户反馈。"""

    skeleton: str
    dependencies: list[tuple[str, str]]
    prior: Optional[str] = None
    feedback: Optional[str] = None

    def assemble_invoke(self) -> str:
        """按固定顺序拼接子 agent 首轮调用消息。"""
        dependency_sections = [
            section(f"[{role_name}] ", output, inline=True)
            for role_name, output in self.dependencies
        ]
        return join_sections([
            self.skeleton,
            section("前置产物（上游已确认的产出）：", "\n".join(dependency_sections)),
            section("上轮产物（被打回的草稿，据此改进，不要简单重复）：", self.prior),
            section("用户反馈（据此改进）：", self.feedback),
        ])
