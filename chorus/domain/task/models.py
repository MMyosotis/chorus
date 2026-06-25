# kitty/domain/task/models.py
"""任务图领域模型：Task / TaskStatus / AgentType / CreationIntent / StepSpec /
TaskArtifacts / TaskStep。

纯 Pydantic 模型，不 import repos/services/hooks/tools/agents。状态语义与转移
规则不在此（见 state_machine.py），这里只承载数据形状。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_CONFIRM = "awaiting_confirm"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    IDEA = "idea"
    SCRIPT = "script"
    IMAGE = "image"
    FINALIZE = "finalize"


class Task(BaseModel):
    """tasks 表一行的领域模型。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    session_id: str
    pipeline_id: str
    agent_type: str  # AgentType 值
    seq: int
    status: str  # TaskStatus 值
    invoke_message: str
    dependencies: list[str] = Field(default_factory=list)  # 前置 task_id 列表
    feedback: Optional[dict] = None  # retry 时注入的用户反馈
    error: Optional[str] = None
    created_at: float
    updated_at: float


class TaskArtifacts(BaseModel):
    """task_artifacts 表一行的领域模型（1:1 关联 tasks，大 JSON 产物）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    step_output: Optional[Any] = None  # 下游注入用（= artifacts 同值）
    artifacts: Optional[Any] = None  # 前端渲染用结构化产物
    narrative: Optional[dict] = None  # 角色话术


class TaskStep(BaseModel):
    """task_steps 表一行的领域模型（1:N，每轮 ReAct 一行）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    task_id: str
    iteration: int  # 1-based
    thinking: Optional[str] = None
    text: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_results: Optional[list[dict]] = None
    finish_reason: Optional[str] = None
    created_at: float


@dataclass
class CreationIntent:
    """supervisor 从 create_plan 工具参数解析的创作意图。"""

    topic: str
    style: str = ""
    image_count: int = 3
    extra: dict = field(default_factory=dict)


@dataclass
class StepSpec:
    """模型自主编排的单步规格（建图前形态，落库前 deps 是索引，落库后解析为 task_id）。"""

    agent_type: str  # AgentType 值
    deps: list[int]  # 引用 steps 内前置步骤索引（0-based）
    focus: str
