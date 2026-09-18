"""tasks / task_content 核心行模型 + 任务图共享词汇表（状态/角色枚举）。

数据模型带只读行为：任务持可调度判定。"""
from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional

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
    # 触发建图的助手消息；由此计划产生的审核卡都以它为锚点。
    message_id: Optional[str] = None
    dependencies: list[str] = Field(default_factory=list)
    owner_id: Optional[float] = None

    def can_schedule(self, deps: Iterable["Task"]) -> bool:
        """可调度：待执行且所有依赖均已完成。失败的上游会阻塞后继。"""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep.status == TaskStatus.FINISHED for dep in deps)

    def is_delivered(self) -> bool:
        """判断任务是否为已交付成品。"""
        return self.agent_type == AgentType.FINALIZE and self.status == TaskStatus.FINISHED


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskContent:
    """task_content 表行。"""

    task_id: str
    invoke_message: str
    error: Optional[str] = None
    feedback: Optional[str] = None
