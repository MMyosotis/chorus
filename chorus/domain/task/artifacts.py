"""task_artifacts 表的全部产物模型：结构化产物 + 角色话术 + 成品契约。
纯数据形状，按角色多态，与表一一对应。"""
from __future__ import annotations

import dataclasses
import json
from functools import singledispatch
from typing import Any, Optional, Union

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.errors import ValidationError


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskArtifacts:
    """任务产物行：结构化产物按角色多态。"""

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
class PostCardMeta:
    """成品卡剥离的资源引用元数据，空默认容忍历史落库行。"""

    preview_ref: str = ""
    stylesheet_ref: str = ""
    title: str = ""


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class PostCard:
    """成品卡片：标准 markdown 正文 + 剥离的资源引用元数据。"""

    markdown: str
    meta: PostCardMeta = Field(default_factory=PostCardMeta)


@singledispatch
def invoke_text(artifacts: Any) -> str:
    """产物喂回模型的文本：结构化产物给全量 JSON。"""
    return json.dumps(dataclasses.asdict(artifacts), ensure_ascii=False, indent=2)


@invoke_text.register
def _script_text(artifacts: ScriptArtifacts) -> str:
    return artifacts.markdown


@invoke_text.register
def _postcard_text(artifacts: PostCard) -> str:
    return artifacts.markdown


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ArtifactEdit:
    """人工编辑载荷：按产物类型各取所需字段。"""

    candidates: Optional[list[IdeaCandidate]] = None
    markdown: Optional[str] = None


@singledispatch
def build_edited_artifacts(current: Any, edit: ArtifactEdit) -> Any:
    """人工编辑载荷按产物类型合成新产物，未注册的类型拒绝编辑。"""
    raise ValidationError("该角色产物不支持编辑", "只有选题、文案与成品可人工编辑")


@build_edited_artifacts.register
def _idea_edit(current: IdeaArtifacts, edit: ArtifactEdit) -> IdeaArtifacts:
    """选题编辑候选字段，选中项保持。"""
    return IdeaArtifacts(candidates=list(edit.candidates), selected=current.selected)


@build_edited_artifacts.register
def _script_edit(current: ScriptArtifacts, edit: ArtifactEdit) -> ScriptArtifacts:
    return ScriptArtifacts(markdown=edit.markdown)


@build_edited_artifacts.register
def _postcard_edit(current: PostCard, edit: ArtifactEdit) -> PostCard:
    """成品编辑只换正文，资源元数据保留。"""
    return PostCard(markdown=edit.markdown, meta=current.meta)
