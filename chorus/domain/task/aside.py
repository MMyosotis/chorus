"""运行期 agent 旁白:读任务说明调小模型生成一句进行态描述,失败兜默认文案。"""
from __future__ import annotations

from chorus.domain.bypass import BypassCaller, BypassScope
from chorus.domain.log import get_logger
from chorus.domain.task.models import AgentType

_logger = get_logger("domain.task.aside")

_ASIDE_MAX_LEN = 30
_ROLE_HINT: dict[AgentType, str] = {
    AgentType.IDEA: "选题官",
    AgentType.SCRIPT: "文案官",
    AgentType.IMAGE: "配图官",
    AgentType.FINALIZE: "排版官",
}
_DEFAULT_ASIDE: dict[AgentType, str] = {
    AgentType.IDEA: "我正在调研候选选题",
    AgentType.SCRIPT: "我正在撰写正文",
    AgentType.IMAGE: "我正在生成配图",
    AgentType.FINALIZE: "我正在排版成品",
}


class AsideGenerator:
    """基于任务说明生成一句任务级进行态描述,失败兜默认文案。"""

    def __init__(self, bypass: BypassCaller):
        self._bypass = bypass

    def generate(self, agent_type: AgentType, invoke: str, scope: BypassScope) -> str:
        fallback = _DEFAULT_ASIDE[agent_type]
        role = _ROLE_HINT[agent_type]
        prompt = (
            f"你是{role}。请基于以下任务说明，用一句话（不超过20字）以第一人称描述你正在做什么，"
            "直白、功能性、不文艺、不画面感，仅返回这句话。\n\n"
            f"<task_description>\n{invoke[:500]}\n</task_description>"
        )
        try:
            raw = self._bypass.call(prompt, 512, "aside", scope)
        except Exception:
            _logger.exception("aside generation failed, fallback")
            return fallback
        return raw[:_ASIDE_MAX_LEN] if raw else fallback
