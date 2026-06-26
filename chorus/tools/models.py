"""工具领域模型。

ToolSchema：OpenAI function 描述（frozen，format 转 provider 格式）。
ToolCall：规范化后的工具调用（arguments 已 json.loads），供 agent loop 流转。
工具执行结果不单独建模——content 在 ToolOutcome（Reply/Terminal）上，duration_ms 在
DispatchResult 上，由 dispatch 直接产出，不经中间模型。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ToolSchema:
    """OpenAI function 描述。"""

    name: str
    description: str
    parameters: dict

    def format(self) -> dict:
        return {"type": "function", "function": asdict(self)}


@dataclass(frozen=True)
class ToolCall:
    """规范化后的工具调用（arguments 已 json.loads）。"""

    id: str
    name: str
    arguments: dict
