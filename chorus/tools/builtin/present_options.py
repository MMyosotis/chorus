"""选项征询工具：一次提出一组选择题，整组作答后才续跑 loop。"""

from __future__ import annotations

from typing import Optional

from chorus.domain.events import OptionPromptEvent
from chorus.domain.option import OptionAnswer, OptionQuestion
from chorus.services.option import OptionPromptService
from chorus.tools.framework import Reply, Suspend, Tool, ToolContext, ToolRunResult

_CUSTOM_SIGNAL = "__custom__"


class PresentOptionsTool(Tool):
    name = "present_options"
    description = (
        "当你需要向用户征询一个或多个选择时调用。将同一轮可独立回答的问题放进 questions，"
        "用户会依次完成所有题目，整组答案会一次性作为工具结果回传给你继续。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 1,
                "description": "同一轮可独立回答的选择题，不要每题单独调用工具",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 4,
                            "description": "候选选项",
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
                            "description": "是否允许用户自由输入",
                            "default": True,
                        },
                    },
                    "required": ["question", "options"],
                },
            },
        },
        "required": ["questions"],
    }
    running_label = "征询用户选择"

    def __init__(self, option_service: OptionPromptService):
        self._options = option_service

    def display(self, arguments: dict) -> str:
        questions = arguments.get("questions") or []
        return f"征询选择（{len(questions)} 项）"

    def _build_question(self, raw: dict) -> OptionQuestion:
        items = [
            {"signal": str(idx), "label": item["label"], "description": item["description"]}
            for idx, item in enumerate(raw["options"])
        ]
        return OptionQuestion.model_validate({
            "question": raw["question"],
            "options": items,
            "allow_custom": raw.get("allow_custom", True),
        })

    def run(self, arguments: dict, ctx: ToolContext) -> ToolRunResult:
        try:
            raw_questions = arguments["questions"]
            questions = [self._build_question(raw) for raw in raw_questions]
        except (KeyError, TypeError, ValueError) as e:
            return ToolRunResult(Reply(f"present_options 参数缺失或格式错: {e}"))

        prompt = self._options.create(
            session_id=ctx.session_id,
            questions=questions,
            message_id=ctx.message_id,
        )
        event = OptionPromptEvent(
            prompt_id=prompt.prompt_id,
            message_id=prompt.message_id,
            questions=[question.model_dump() for question in prompt.questions],
        )
        return ToolRunResult(
            Suspend(f"已向用户征询选择（{len(questions)} 项），等待用户完成作答。"),
            events=(event,),
        )

    def _resolve_question(
        self, question: OptionQuestion, submitted: dict,
    ) -> tuple[OptionAnswer, str]:
        submitted_signal = submitted.get("signal")
        if submitted_signal == _CUSTOM_SIGNAL:
            custom_text = (submitted.get("custom_text") or "").strip()
            answer = OptionAnswer(
                signal=submitted_signal,
                label="补充你的想法",
                custom_text=custom_text,
            )
            receipt = f"{question.question}：{custom_text}"
        else:
            label = next(
                option.label for option in question.options if option.signal == submitted_signal
            )
            answer = OptionAnswer(signal=submitted_signal, label=label)
            receipt = f"{question.question}：{label}"
        return answer, receipt

    def resolve_external(
        self, session_id: str, signal: str, payload: Optional[dict] = None,
    ) -> str:
        answers = (payload or {})["answers"]
        prompt = self._options.get_open(session_id)

        resolved = []
        receipts = []
        for question, submitted in zip(prompt.questions, answers):
            answer, receipt = self._resolve_question(question, submitted)
            resolved.append(answer)
            receipts.append(receipt)

        self._options.mark_answered(session_id, resolved)
        return "用户已完成本组选择：" + "；".join(receipts)
