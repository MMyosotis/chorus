"""tasks / task_content 核心行模型 + 任务图共享词汇表（状态/角色枚举）。

数据模型带只读行为：任务持可调度判定，内容行持调用消息渲染。"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Iterable, Optional

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

    def can_schedule(self, deps: Iterable["Task"]) -> bool:
        """可调度：待执行且所有依赖均已完成。失败的上游会阻塞后继。"""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep.status == TaskStatus.FINISHED for dep in deps)


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskContent:
    """task_content 表行。"""

    task_id: str
    invoke_message: str
    progress_total: Optional[int] = None
    error: Optional[str] = None
    feedback: Optional[str] = None

    def render_invoke(
        self, deps_outputs: dict[str, Any], self_prior: Optional[Any],
    ) -> str:
        """拼首轮调用消息：基础骨架，按需附前置产物、上轮产物、用户反馈。"""
        parts = [self.invoke_message]
        if deps_outputs:
            parts.append("前置步骤产物：")
            for dep_id, out in deps_outputs.items():
                parts.append(f"--- {dep_id} ---\n{json.dumps(out, ensure_ascii=False, indent=2)}")

        if self_prior is not None:
            parts.append("你上一轮的产物（据此定向改进，不要简单重复）：")
            parts.append(json.dumps(self_prior, ensure_ascii=False, indent=2))

        if self.feedback:
            parts.append("用户反馈（请据此改进）：")
            parts.append(self.feedback)

        return "\n\n".join(parts)
