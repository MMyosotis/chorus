"""选项征询工具：向用户出选择题，挂起等用户作答后续跑 loop。"""

from __future__ import annotations

from typing import Optional

from chorus.domain.events import OptionPromptEvent
from chorus.domain.option import OptionAnswer, OptionItem
from chorus.services.option import OptionPromptService
from chorus.tools.framework import Reply, Suspend, Tool, ToolContext, ToolRunResult

_CUSTOM_SIGNAL = "__custom__"


class PresentOptionsTool(Tool):
    name = "present_options"
    description = (
        "当你需要向用户征询选择时调用：给出问题和若干选项，"
        "用户选择后结果会作为工具结果回传给你继续。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要问用户的问题，一句话标题",
            },
            "options": {
                "type": "array",
                "minItems": 3,
                "maxItems": 4,
                "description": "候选选项，3 到 4 个",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "选项标题"},
                        "description": {"type": "string", "description": "选项的简短解释"},
                    },
                    "required": ["label", "description"],
                },
            },
            "allow_custom": {
                "type": "boolean",
                "description": "是否允许用户自由输入而非选给定项，默认 true",
                "default": True,
            },
        },
        "required": ["question", "options", "allow_custom"],
    }
    running_label = "征询用户选择"

    def __init__(self, option_service: OptionPromptService):
        self._options = option_service

    def display(self, arguments: dict) -> str:
        question = (arguments.get("question") or "").strip()
        return f"征询：{question[:36]}"

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        try:
            question = arguments["question"]
            raw_options = arguments["options"]
            allow_custom = arguments.get("allow_custom", True)
            items = [
                OptionItem(signal=str(idx), label=opt["label"], description=opt["description"])
                for idx, opt in enumerate(raw_options)
            ]
        except (KeyError, TypeError, IndexError) as e:
            return ToolRunResult(Reply(f"present_options 参数缺失或格式错: {e}"))

        prompt = self._options.create(
            session_id=ctx.session_id,
            question=question,
            options=items,
            allow_custom=allow_custom,
            message_id=ctx.message_id,
        )
        event = OptionPromptEvent(
            prompt_id=prompt.prompt_id,
            message_id=prompt.message_id,
            question=prompt.question,
            options=[item.model_dump() for item in prompt.options],
            allow_custom=prompt.allow_custom,
        )
        return ToolRunResult(
            Suspend(f"已向用户征询选择：{prompt.question}（{len(items)} 个选项），等待用户作答。"),
            events=(event,),
        )

    def resolve_external(self, session_id: str, signal: str, payload: Optional[dict] = None) -> str:
        prompt = self._options.get_open(session_id)
        if signal == _CUSTOM_SIGNAL:
            custom_text = ((payload or {}).get("custom_text") or "").strip()
            self._options.mark_answered(
                session_id,
                OptionAnswer(signal=signal, label="补充你的想法", custom_text=custom_text),
            )
            return f"用户自由补充：{custom_text or '（空）'}"
        label = next((option.label for option in prompt.options if option.signal == signal))
        self._options.mark_answered(session_id, OptionAnswer(signal=signal, label=label))
        return f"用户选择了：{label}"
