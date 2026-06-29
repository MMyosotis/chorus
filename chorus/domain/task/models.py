# kitty/domain/task/models.py
"""任务图领域模型：Task / TaskStatus / AgentType / CreationIntent / StepSpec /
TaskArtifacts / TaskStep。

纯 Pydantic 模型，不 import repos/services/hooks/tools/agents。状态语义与转移
规则不在此（见 state.py），这里只承载数据形状。

pydantic dataclass 走位置参数 __init__，无默认值字段必须排在有默认值字段之前。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

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
    """tasks 表一行的领域模型。"""

    id: str
    session_id: str
    pipeline_id: str
    agent_type: str  # AgentType 值
    seq: int
    status: str  # TaskStatus 值
    invoke_message: str
    created_at: float
    updated_at: float
    dependencies: list[str] = Field(default_factory=list)  # 前置 task_id 列表
    feedback: Optional[dict] = None  # retry 时注入的用户反馈
    error: Optional[str] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskArtifacts:
    """task_artifacts 表一行的领域模型（1:1 关联 tasks，大 JSON 产物）。

    artifacts 既是前端渲染用的结构化产物，也作下游注入数据——二者同源同值，
    故只存一列（曾分 step_output/artifacts 两列，物理冗余已合并）。
    """

    task_id: str
    artifacts: Optional[Any] = None  # 结构化产物：前端渲染用 + 下游注入用（同值）
    narrative: Optional[dict] = None  # 角色话术（Narrative 校验后 asdict 入库）


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class Narrative:
    """subagent 产出的角色话术——parse 期强校验值对象，校验后 asdict 回 dict 入库。

    awaiting_line: HIL 等待确认引导语（awaiting_confirm 态展示）；
    done_line: 完成总结一句话（finished 态展示）。执行完一次性产出。
    """

    awaiting_line: str
    done_line: str


# ---- artifacts 内容模型（parse 期强校验值对象，校验后 asdict 回 dict 入库）----
# 与 Narrative 同层：存储行模型 TaskArtifacts.artifacts 仍是松 Any（落 JSON blob），
# 这里的模型只在 parse_output 校验时一次性构造，验完即 asdict。finalize 复用 PostCard。

@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class IdeaCandidate:
    index: int
    title: str
    angle: str
    reason: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class IdeaArtifacts:
    """idea 角色产物：候选选题列表 + 选中索引（selected 由 HIL 确认后写入，parse 期可空）。"""

    candidates: list[IdeaCandidate]
    selected: Optional[int] = None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ScriptBlock:
    kind: str  # heading/paragraph/list 等（中间产物，不强制 Literal，留弹性）
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
    text: str = ""  # paragraph/heading/quote 文本; list 用 \n 分条
    image: Optional[PostImage] = None  # kind=image 时必填


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostCard:
    """finalize 角色产物（= 成品契约）：博文卡片树，前端 PostCard.vue 拿到即渲染。

    kind 枚举固定有界，前端按 kind 套样式，不猜内容格式。
    """

    title: str
    sections: list[PostSection]
    cover: Optional[PostImage] = None
    tags: list[str] = Field(default_factory=list)
    summary: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskStep:
    """task_steps 表一行的领域模型（1:N，每轮 ReAct 一行）。"""

    id: str
    task_id: str
    iteration: int  # 1-based
    created_at: float
    thinking: Optional[str] = None
    text: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_results: Optional[list[dict]] = None
    finish_reason: Optional[str] = None


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
