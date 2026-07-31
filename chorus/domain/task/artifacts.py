"""task_artifacts 表的全部产物模型：结构化产物 + 角色话术 + 成品契约。
纯数据形状，按角色多态，与表一一对应。"""
from __future__ import annotations

import dataclasses
from functools import singledispatch
from typing import Any, Optional, Union

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass as pydataclass


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskArtifacts:
    """任务产物行：结构化产物。"""

    task_id: str
    artifacts: Optional[Union["IdeaArtifacts", "ScriptArtifacts", "ImageArtifacts", "PostCard"]] = None


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

    def selected_candidate(self) -> Optional[IdeaCandidate]:
        """生效选中项：selected 有效则取它，否则回退首个候选。"""
        if self.selected is not None and 0 <= self.selected < len(self.candidates):
            return self.candidates[self.selected]
        return self.candidates[0] if self.candidates else None


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ScriptArtifacts:
    """文案官产物：原始 markdown 正文。"""

    markdown: str


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ImageItem:
    url: str
    caption: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ImageArtifacts:
    """配图官产物：配图列表。"""

    images: list[ImageItem]


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostCard:
    """成品卡片：标准 markdown 正文 + 剥离的资源引用元数据。"""

    markdown: str
    meta: dict[str, Any] = Field(default_factory=dict)


@singledispatch
def downstream_view(artifacts: Any) -> dict:
    """产物转下游注入视图，默认全量。"""
    return dataclasses.asdict(artifacts)


@downstream_view.register
def _idea_view(artifacts: IdeaArtifacts) -> dict:
    """选题裁剪到生效选中候选。"""
    cand = artifacts.selected_candidate()
    return {"candidates": [dataclasses.asdict(cand)]} if cand else {}
