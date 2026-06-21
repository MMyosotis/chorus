"""system prompt 装配：base 文案 + 拼装规则同住一处。

SYSTEM_PROMPT 是默认人设文案（PromptContext.base 的默认值）；build_system_prompt
按规则把 base + 非空各段拼成最终 system prompt 字符串。本模块纯领域，零基础设施依赖。

PromptContext 是扩展点：未来要加入运行时多方信息（对话摘要、用户画像、工具清单等），
只需加字段 + 在 build_system_prompt 里加一段拼接，签名稳定。base 可在构造时覆盖，
便于测试。
"""

from __future__ import annotations

from dataclasses import dataclass

# 默认人设文案；PromptContext.base 未显式提供时取它。
SYSTEM_PROMPT = (
    "你是一个友好、健谈的 AI 助手。记住对话中提到过的信息，保持上下文连贯。\n"
    "你需要先调用output_plan输出你的执行计划，然后可以调用工具完成任务"
)


@dataclass(frozen=True)
class PromptContext:
    """system prompt 装配所需的多方信息。

    扩展时新增字段即可，不必改装配函数签名。
    """

    base: str = SYSTEM_PROMPT
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
