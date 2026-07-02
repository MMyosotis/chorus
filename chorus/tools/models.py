"""工具领域模型：工具描述与规范化调用。执行结果不单独建模，由框架层直接产出。"""

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
