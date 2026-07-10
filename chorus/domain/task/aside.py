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
    "idea": "我在琢磨一个好选题",
    "script": "我在打磨这段文案",
    "image": "我在构思一张画面",
    "finalize": "我在收拢这篇成稿",
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
            f"你是{role}。请基于以下任务说明，用一句话（不超过20字）描述你接下来打算怎么写，"
            "要有画面感、文艺、第一人称口吻，仅返回这句话。\n\n"
            f"{invoke[:500]}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=48,
                stream=False,
            )
            raw = (resp.choices[0].message.content or "").strip().strip("\"'`")
        except Exception:
            return fallback
        return raw[:_ASIDE_MAX_LEN] if raw else fallback
