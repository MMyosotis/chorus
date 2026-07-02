"""任务图领域模型：任务、步骤、产物等数据形状。

纯数据模型，不含状态转移规则。无默认值字段须排在有默认值字段之前。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, Union

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


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskArtifacts:
    """任务产物行：结构化产物与角色话术。"""

    task_id: str
    artifacts: Optional[Union["IdeaArtifacts", "ScriptArtifacts", "ImageArtifacts", "PostCard"]] = None
    narrative: Optional["Narrative"] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class Narrative:
    """角色话术：等待确认与完成总结两句，执行完一次性产出。"""

    awaiting_line: str
    done_line: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class IdeaCandidate:
    index: int
    title: str
    angle: str
    reason: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class IdeaArtifacts:
    """选题产物：候选列表，选中项待确认后写入。"""

    candidates: list[IdeaCandidate]
    selected: Optional[int] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ScriptBlock:
    kind: str
    text: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ScriptArtifacts:
    """script 角色产物：正文块序列。"""

    blocks: list[ScriptBlock]


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ImageItem:
    url: str
    caption: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ImageArtifacts:
    """image 角色产物：配图列表。"""

    images: list[ImageItem]


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostImage:
    url: str
    caption: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostSection:
    kind: Literal["paragraph", "heading", "list", "quote", "image"]
    text: str = ""
    image: Optional[PostImage] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostCard:
    """成品卡片：博文结构树，前端按节点类型渲染。"""

    title: str
    sections: list[PostSection]
    cover: Optional[PostImage] = None
    tags: list[str] = Field(default_factory=list)
    summary: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class SearchResultsPayload:
    """tool_done(baidu_search) 的载荷：搜索结果摘要。"""

    total: int
    bullets: list[dict]


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ImageProgressPayload:
    """tool_done(generate_image) 的载荷：配图进度与预览。"""

    current: int
    items: list[dict]
    total: Optional[int] = None
    unit: str = "张图"


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class FailedPayload:
    """failed 事件的载荷：失败详情。"""

    detail_md: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskActivity:
    """活动流一行：核心字段 + tool_name + 多态 payload。"""

    id: int
    task_id: str
    event_type: str
    role_line: str
    status: str
    created_at: float
    tool_name: Optional[str] = None
    payload: Optional[Union["SearchResultsPayload", "ImageProgressPayload", "FailedPayload"]] = None


@dataclass
class CreationIntent:
    """从建图工具参数解析的创作意图。"""

    topic: str
    style: str = ""
    image_count: int = 3
    extra: dict = field(default_factory=dict)


@dataclass
class StepSpec:
    """建图前的单步规格，落库后依赖由索引解析为任务标识。"""

    agent_type: str
    deps: list[int]
    focus: str
