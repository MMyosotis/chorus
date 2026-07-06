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
            "interaction_intent": {
                "type": "string",
                "enum": [
                    "smalltalk",
                    "create_content",
                    "clarify_existing",
                    "modify_intent",
                    "confirm_intent",
                    "reject_intent",
                    "cancel_task",
                    "ask_status",
                    "give_feedback",
                ],
                "description": "当前用户话语的交互意图",
            },
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
                "description": "当前结构化意图成熟度",
            },
            "goal": {"type": "string", "description": "一句话概括用户目标"},
            "known_slots": {
                "type": "object",
                "description": "已识别的关键槽位，例如 platform/output_type/topic/style/image_count/constraints",
            },
            "missing_slots": {
                "type": "array",
                "items": {"type": "string"},
                "description": "仍缺失、会影响执行派发的槽位",
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "接下来要问用户的具体问题",
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
            "next_action": {
                "type": "string",
                "enum": [
                    "reply_only",
                    "ask_user",
                    "wait_user_confirm",
                    "create_plan_after_confirm",
                    "dispatching",
                    "blocked",
                ],
                "description": "主流程下一步动作",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "你对当前意图理解准确性的置信度",
            },
        },
        "required": [
            "interaction_intent",
            "intent_status",
            "goal",
            "known_slots",
            "missing_slots",
            "open_questions",
            "confirmation_summary",
            "next_action",
            "confidence",
        ],
    }
    running_label = "更新意图理解"

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
        return Reply(
            "intent_state updated: "
            f"status={state.intent_status}, next_action={state.next_action}, version={state.version}"
        )
