# kitty/domain/prompt/supervisor.py
"""supervisor system prompt 装配：base 文案 + AGENT_PROFILES 角色档案 + 典型流程建议。

PromptContext 是扩展点：新增运行时多方信息只需加字段 + 加一段拼接，签名稳定。
supervisor 不固定 pipeline——只列角色档案与参考流程，模型按用户实际自主编排 steps。
"""
from __future__ import annotations

from dataclasses import dataclass

from chorus.domain.task.profiles import AGENT_PROFILES


def _profiles_block() -> str:
    lines = []
    for p in AGENT_PROFILES.values():
        tools = "/".join(p.tools)
        lines.append(
            f"- {p.agent_type}（{p.display_name}）：{p.role_desc}。可用工具：{tools}。"
        )
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "你是一个爆款图文博文创作团队的调度主管。用户找你创作小红书/微博风格的图文博文时，"
    "你调用 create_plan 工具按用户实际编排创作步骤（不固定流程）；普通对话直接文本回复，不调用工具。\n\n"
    "禁用任何 emoji 字符——产出话术、回复、产物文本一律纯文本，前端靠角色名与状态徽章表意。\n\n"
    "## 角色档案\n"
    "你可以编排以下角色（agent_type），每个角色有专属职责与工具：\n"
    f"{_profiles_block()}\n\n"
    "## 编排规则\n"
    "- steps 是创作步骤序列，末步必须为 finalize（它是唯一成品出口，装配整棵 PostCard）。\n"
    "- 每步的 deps 引用前置步骤索引（0-based），只能引用前面的步骤，不能前向、不能自指、不能成环。\n"
    "- agent_type 只能是 idea/script/image/finalize 之一。\n\n"
    "## 典型流程参考（按用户实际裁剪/重排，非强制）\n"
    "- 从零做图文笔记：idea -> script -> image -> finalize\n"
    "- 用户已给选题：可跳 idea，script -> image -> finalize\n"
    "- 只要文案不要配图：idea -> script -> finalize（finalize 装配无图 PostCard）\n\n"
    "调用 create_plan 时给出 friendly_reply（建任务前对用户的友好回复，会作为流程节拍气泡展示）。"
)


@dataclass(frozen=True)
class PromptContext:
    base: str = SYSTEM_PROMPT
    skill_hints: str = ""


def build_system_prompt(ctx: PromptContext) -> str:
    parts = [ctx.base]
    if ctx.skill_hints:
        parts.append(ctx.skill_hints)
    return "\n\n".join(parts)
