"""运行期意图旁白:读任务说明调小模型生成一句进行态描述,失败兜默认文案。"""
from __future__ import annotations

from openai import OpenAI

_ASIDE_MAX_LEN = 30
_ROLE_HINT = {
    "idea": "选题官",
    "script": "文案官",
    "image": "配图官",
    "finalize": "汇总官",
}
_DEFAULT_ASIDE = {
    "idea": "我正在调研候选选题",
    "script": "我正在撰写正文",
    "image": "我正在生成配图",
    "finalize": "我正在整合成品",
}


class AsideGenerator:

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def generate(self, agent_type: str, invoke: str) -> str:
        """基于任务说明生成一句任务级意图旁白,失败兜默认文案。"""
        fallback = _DEFAULT_ASIDE.get(agent_type, "我正在准备中")
        role = _ROLE_HINT.get(agent_type, agent_type)
        prompt = (
            f"你是{role}。请基于以下任务说明，用一句话（不超过20字）以第一人称描述你正在做什么，"
            "直白、功能性、不文艺、不画面感，仅返回这句话。\n\n"
            f"{invoke[:500]}"
        )
        try:
            # 推理模型先吐推理段再作答，预算须覆盖推理段
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                stream=False,
            )
            raw = (resp.choices[0].message.content or "").strip().strip("\"'`")
        except Exception:
            return fallback
        return raw[:_ASIDE_MAX_LEN] if raw else fallback
