"""运行期意图旁白:读 invoke 调小模型生成一句进行态描述,fail-open。"""
from __future__ import annotations

from typing import Optional

from openai import OpenAI

_ASIDE_MAX_LEN = 30
_ROLE_HINT = {
    "idea": "选题官",
    "script": "文案官",
    "image": "配图官",
    "finalize": "汇总官",
}


class AsideGenerator:
    """围绕旁白概念的单概念 infra service:调外部模型,非流式短输出。"""

    def __init__(self, client: OpenAI, model_id: str):
        self._client = client
        self._model = model_id

    def generate(self, agent_type: str, invoke: str) -> Optional[str]:
        """基于 invoke 生成一句任务级意图旁白,失败返回 None。"""
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
            return None
        return raw[:_ASIDE_MAX_LEN] if raw else None
