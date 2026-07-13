"""主 Agent 的意图状态更新工具。"""

from __future__ import annotations

from pydantic import ValidationError

from chorus.domain.intent import IntentStatePatch
from chorus.services.intent_state import IntentStateService
from chorus.tools.framework import Reply, Terminal, Tool, ToolContext


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
                    "ready_to_confirm=信息齐全，填好 confirmation_summary 标题等用户拍板；"
                    "confirmed/dispatched 由系统翻转，模型不要主动填"
                ),
            },
            "goal": {"type": "string", "description": "一句话概括用户目标"},
            "known_slots": {
                "type": "object",
                "description": "已识别的关键槽位，key 用中文短词（平台/体裁/主题/风格/配图/约束等），value 用自然语言",
            },
            "missing_slots": {
                "type": "array",
                "items": {"type": "string"},
                "description": "仍缺失、会影响执行派发的槽位，用中文短词（主题/风格/配图等）",
            },
            "confirmation_summary": {
                "type": ["object", "null"],
                "properties": {
                    "title": {"type": "string"},
                },
                "required": ["title"],
                "description": "ready_to_confirm 时给用户看的一句话确认标题；槽位展示由系统从 known_slots 自动投影，不要在此填 items",
            },
            "friendly_reply": {
                "type": "string",
                "description": "ready_to_confirm 时的确认引导文案，作为本轮节拍气泡展示；其余状态忽略",
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
        try:
            patch = IntentStatePatch(**arguments)
        except ValidationError as e:
            return Reply(f"update_intent_state 参数格式错: {e}")

        state = self._intent.update_from_tool(ctx.session_id, patch)
        if state.intent_status == "ready_to_confirm":
            return Terminal(
                f"intent_state updated: status=ready_to_confirm, "
                f"version={state.version}. 等待用户拍板。"
            )
        return Reply(
            "intent_state updated: "
            f"status={state.intent_status}, version={state.version}"
        )

    def resolve_external(self, session_id: str, signal: str) -> str:
        """用户对确认卡的两类回应：同意进入 confirmed，要求调整回到澄清。"""
        if signal == "confirm":
            state = self._intent.patch_status(session_id, "confirmed")
            return f"用户已同意，意图进入 confirmed（version={state.version}），等待建图"
        state = self._intent.patch_status(session_id, "needs_clarification")
        return f"用户要求继续调整，意图回到 needs_clarification（version={state.version}）"
