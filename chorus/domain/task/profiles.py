"""角色档案注册表：四子角色的展示名、职责、入场台词、产物模型与产物解析。
新增角色只需加一条档案，文案禁 emoji，切段校验还原随档案内聚。"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Type

from pydantic import TypeAdapter
from pydantic import ValidationError as PydValidationError

from chorus.domain.task.artifacts import (
    IdeaArtifacts,
    ImageArtifacts,
    PostCard,
    ScriptArtifacts,
)
from chorus.domain.task.errors import ValidationError
from chorus.domain.task.markdown import (
    parse_idea_md,
    parse_image_md,
    parse_postcard_md,
    parse_script_md,
)
from chorus.domain.task.models import AgentType


@lru_cache(maxsize=None)
def _artifacts_adapter(model: Type[Any]) -> TypeAdapter:
    return TypeAdapter(model)


@dataclass(frozen=True)
class AgentProfile:
    agent_type: AgentType
    display_name: str
    short_name: str
    role_desc: str
    artifacts_schema: str
    artifacts_model: Type[Any]
    artifacts_parser: Callable[[str], Any]
    composing_label: str
    activity_lines: dict = field(default_factory=dict)

    def activity_line(self, kind: str) -> str:
        """按活动态取本角色台词，未声明则空。"""
        return self.activity_lines.get(kind, "")

    def hydrate_artifacts(self, raw: dict) -> Any:
        """把落库 JSON 按本角色产物模型还原成对象。"""
        return _artifacts_adapter(self.artifacts_model).validate_python(raw)

    def parse_output(self, content: str) -> Any:
        """按角色解析 Markdown 正文还原成产物对象，失败附修正提示。"""
        try:
            return self.artifacts_parser(content)
        except PydValidationError as e:
            raise ValidationError(
                f"ARTIFACTS 校验失败: {e}",
                f"{self.display_name}产物须符合 {self.artifacts_model.__name__} 结构",
            ) from e


AGENT_PROFILES: dict[AgentType, AgentProfile] = {
    AgentType.IDEA: AgentProfile(
        agent_type=AgentType.IDEA,
        display_name="选题官",
        short_name="选题",
        role_desc="调研热点、琢磨选题，给出候选标题与切入角度；只找选题方向，不备正文素材、不写正文、不出图",
        artifacts_schema="idea",
        artifacts_model=IdeaArtifacts,
        artifacts_parser=parse_idea_md,
        composing_label="个候选",
        activity_lines={
            "thinking": "正在梳理选题",
            "searching": "正在搜索",
            "composing": "正在撰写",
        },
    ),
    AgentType.SCRIPT: AgentProfile(
        agent_type=AgentType.SCRIPT,
        display_name="文案官",
        short_name="文案",
        role_desc="基于选题产物展开图文博文正文；只写正文，不重新选题、不出图",
        artifacts_schema="script",
        artifacts_model=ScriptArtifacts,
        artifacts_parser=parse_script_md,
        composing_label="段",
        activity_lines={
            "thinking": "正在构思文案",
            "searching": "正在搜索",
            "composing": "正在撰写",
        },
    ),
    AgentType.IMAGE: AgentProfile(
        agent_type=AgentType.IMAGE,
        display_name="配图官",
        short_name="配图",
        role_desc="按正文需要生成配图并配图注；只配图，不写正文、不重新选题",
        artifacts_schema="image",
        artifacts_model=ImageArtifacts,
        artifacts_parser=parse_image_md,
        composing_label="张",
        activity_lines={
            "thinking": "正在构思配图",
            "drawing": "正在生成图片",
            "composing": "正在撰写",
        },
    ),
    AgentType.FINALIZE: AgentProfile(
        agent_type=AgentType.FINALIZE,
        display_name="排版官",
        short_name="排版",
        role_desc="装配前三步原料成整棵 PostCard 成品，是唯一成品出口；不新增内容、不搜索",
        artifacts_schema="postcard",
        artifacts_model=PostCard,
        artifacts_parser=parse_postcard_md,
        composing_label="节",
        activity_lines={
            "thinking": "正在梳理结构",
            "composing": "正在撰写",
        },
    ),
}
