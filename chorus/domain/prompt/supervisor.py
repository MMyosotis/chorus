"""supervisor system prompt 模版：基础文案 + 角色档案 + 流程参考。

不固定创作流程，由模型按用户实际编排步骤。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from chorus.config import TOOL_WHITELISTS
from chorus.domain.intent import IntentState
from chorus.domain.task.profiles import AGENT_PROFILES


def _profiles_block() -> str:
    lines = []
    for profile in AGENT_PROFILES.values():
        tools = "/".join(TOOL_WHITELISTS[profile.agent_type])
        lines.append(
            f"- {profile.agent_type}（{profile.display_name}）：{profile.role_desc}。可用工具：{tools}。"
        )
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "你是一个图文创作产品的主 Agent，首要职责是和用户对话、理解并细化用户意图。"
    "你需要自然语言回复用户，同时维护结构化的 current_intent_state。"
    "只有当用户确认意图后，才调用 create_plan 创建任务。\n\n"
    "禁用任何 emoji 字符——产出话术、回复、产物文本一律纯文本，前端靠角色名与状态徽章表意。\n\n"
    "## 意图识别规则\n"
    "- 每个用户回合结束前，除非你正在 confirmed 后创建任务，否则必须调用 update_intent_state。\n"
    "- update_intent_state 表示你当前理解到了哪里、还缺什么、下一步应该问什么或是否等待确认。\n"
    "- 如果信息不足，不要调用 create_plan；先用自然语言追问，并把 intent_status 设为 needs_clarification。\n"
    "- 如果信息足够执行，把 intent_status 设为 ready_to_confirm，confirmation_summary 填给用户确认的摘要，next_action 设为 wait_user_confirm。\n"
    "- 用户没有确认前，create_plan 会被系统拒绝；不要试图绕过确认。\n"
    "- 当 current_intent_state.intent_status 为 confirmed，且用户已确认开始时，你应调用 create_plan。\n\n"
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
    intent_state: IntentState | None = None
    force_directive: str = ""


def build_system_prompt(ctx: PromptContext) -> str:
    parts = [ctx.base]
    if ctx.intent_state is not None:
        parts.append(_intent_state_block(ctx.intent_state))
    if ctx.skill_hints:
        parts.append(ctx.skill_hints)
    if ctx.force_directive:
        parts.append(f"## 本轮系统提醒\n{ctx.force_directive}")
    return "\n\n".join(parts)


def _intent_state_block(state: IntentState) -> str:
    payload = state.public_dict()
    return (
        "## 当前意图状态\n"
        "下面是本会话最新的结构化意图快照。你必须基于它继续对话，"
        "并在本轮结束前用 update_intent_state 写回新的快照。\n"
        "<current_intent_state>\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "</current_intent_state>"
    )
