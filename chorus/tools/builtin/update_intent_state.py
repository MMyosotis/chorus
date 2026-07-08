"""主 Agent 的意图状态更新工具。"""

from __future__ import annotations

from pydantic import ValidationError

from chorus.domain.intent import IntentStatePatch
from chorus.services.intent_state import IntentStateService
from chorus.tools.framework import Reply, Tool, ToolContext


class UpdateIntentStateTool(Tool):
    name = "update_intent_state"
    description = (
        "每轮用户对话后调用，用结构化字段保存你当前对用户意图的理解、缺失信息和下一步。"
        "本工具只更新意图状态，不创建任务。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "intent_status": {
                "type": "string",
                "enum": [
                    "empty",
                    "capturing",
                    "needs_clarification",
                    "ready_to_confirm",
                    "confirmed",
                    "dispatched",
                ],
                "description": (
                    "意图成熟度，按对话推进单调前进："
                    "empty=刚打招呼无创作意图；"
                    "capturing=用户已提创作需求，正在识别槽位（创作必须从此态开始，不要停 empty）；"
                    "needs_clarification=信息不足需追问；"
                    "ready_to_confirm=信息齐全，填好 confirmation_summary 等用户拍板；"
                    "confirmed/dispatched 由系统翻转，模型不要主动填"
                ),
            },
            "goal": {"type": "string", "description": "一句话概括用户目标"},
            "known_slots": {
                "type": "object",
                "description": "已识别的关键槽位，key 用中文短词（平台/体裁/主题/风格/配图数/约束等），value 用自然语言",
            },
            "missing_slots": {
                "type": "array",
                "items": {"type": "string"},
                "description": "仍缺失、会影响执行派发的槽位，用中文短词（主题/风格/配图数等）",
            },
            "confirmation_summary": {
                "type": ["object", "null"],
                "properties": {
                    "title": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["label", "value"],
                        },
                    },
                },
                "required": ["title", "items"],
                "description": "ready_to_confirm 时给用户确认的摘要；未就绪可为 null",
            },
        },
        "required": [
            "intent_status",
            "goal",
            "known_slots",
            "missing_slots",
            "confirmation_summary",
        ],
    }
    running_label = "意图识别中"

    def __init__(self, intent_state: IntentStateService):
        self._intent = intent_state

    def display(self, arguments: dict) -> str:
        status = arguments.get("intent_status", "unknown")
        goal = (arguments.get("goal") or "").strip()
        return f"意图状态：{status} / {goal[:36]}"

    def run(self, arguments: dict, ctx: ToolContext):
        if not ctx.session_id:
            return Reply("update_intent_state 需要 session_id")
        try:
            patch = IntentStatePatch(**arguments)
        except ValidationError as e:
            return Reply(f"update_intent_state 参数格式错: {e}")
        state = self._intent.update_from_tool(ctx.session_id, patch)
        # 返 Reply 不杀轮次：记状态只是规划辅助，终止权交还模型 + after_text nag 兜底，
        # 让模型接着把追问/确认的话说出来，而非工具擅自终结回合。
        return Reply(
            "intent_state updated: "
            f"status={state.intent_status}, version={state.version}"
        )
