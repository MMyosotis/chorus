"""system prompt 装配领域逻辑。

build_system_prompt 接收一个 PromptContext（已由 application 层收集好的多方信息），
按规则拼装成最终 system prompt 字符串。本模块纯领域：不收集信息（那是编排层的活），
只负责拼装，零基础设施依赖，便于单测。

PromptContext 是扩展点：未来要加入运行时多方信息（对话摘要、用户画像、工具清单等），
只需加字段 + 在 build_system_prompt 里加一段拼接，签名稳定。
"""

from __future__ import annotations

from dataclasses import dataclass

from kitty.domain.models.skill import SkillSummary


@dataclass(frozen=True)
class PromptContext:
    """system prompt 装配所需的多方信息（由 application 层收集后注入）。

    扩展时新增字段即可，不必改装配函数签名。
    """

    base: str
    skill_hints: str = ""
    # 未来扩展点示例（按需启用）：
    # conversation_summary: str = ""
    # user_profile: str = ""
    # available_tools: str = ""


def build_system_prompt(ctx: PromptContext) -> str:
    """按规则拼装 system prompt：base + 非空的各段，以空行分隔。"""
    parts = [ctx.base]
    if ctx.skill_hints:
        parts.append(ctx.skill_hints)
    return "\n\n".join(parts)


def format_skill_hints(summaries: list[SkillSummary]) -> str:
    """生成 skill 摘要文本（作为 PromptContext.skill_hints 的来源），无技能时返回空串。"""
    if not summaries:
        return ""
    lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
    for s in summaries:
        lines.append(f"- **{s.name}**: {s.description}")
    return "\n".join(lines)
