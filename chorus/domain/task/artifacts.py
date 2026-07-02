"""task_artifacts 表的全部产物模型：结构化产物 + 角色话术 + 成品契约。

纯数据形状，按角色多态。与 task_artifacts 表一一对应，由 profiles.build_artifacts 还原。
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass as pydataclass


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
