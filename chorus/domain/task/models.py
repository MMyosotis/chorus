"""tasks / task_content 核心行模型 + 任务图共享词汇表（状态/角色枚举）。

纯数据模型，不含状态转移规则。其余表模型见 artifacts.py / activity.py，建图规格见 pipeline.py。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass as pydataclass


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


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class Task:
    """tasks 表一行的领域模型：调度+身份+状态机。"""

    id: str
    session_id: str
    pipeline_id: str
    agent_type: str
    status: str
    created_at: float
    updated_at: float
    dependencies: list[str] = Field(default_factory=list)
    owner_id: Optional[float] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskContent:
    """task_content 表行。"""

    task_id: str
    invoke_message: str
    progress_total: Optional[int] = None
    error: Optional[str] = None
    feedback: Optional[dict] = None
