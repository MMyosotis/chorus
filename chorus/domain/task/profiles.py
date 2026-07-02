"""角色档案注册表：四子角色的展示名、职责、入场台词与产物模型。

新增角色只需加一条档案。文案纯文本禁 emoji。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type

from chorus.domain.task.models import (
    IdeaArtifacts,
    ImageArtifacts,
    PostCard,
    ScriptArtifacts,
)


@dataclass(frozen=True)
class AgentProfile:
    agent_type: str
    display_name: str
    role_desc: str
    enter_line: str
    artifacts_schema: str
    expected_sections: tuple[str, ...]
    artifacts_model: Type[Any]


AGENT_PROFILES: dict[str, AgentProfile] = {
    "idea": AgentProfile(
        agent_type="idea",
        display_name="选题官",
        role_desc="调研热点、琢磨选题，给出多个候选标题与切入角度",
        enter_line="选题官接单啦，先去翻翻最近的热点",
        artifacts_schema="idea",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=IdeaArtifacts,
    ),
    "script": AgentProfile(
        agent_type="script",
        display_name="文案官",
        role_desc="依据选题撰写图文博文正文，拆成有序块草稿",
        enter_line="文案官接单啦，开始码字",
        artifacts_schema="script",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=ScriptArtifacts,
    ),
    "image": AgentProfile(
        agent_type="image",
        display_name="配图官",
        role_desc="为博文生成配图，给出图片列表与图注",
        enter_line="配图官接单啦，准备出图",
        artifacts_schema="image",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=ImageArtifacts,
    ),
    "finalize": AgentProfile(
        agent_type="finalize",
        display_name="汇总官",
        role_desc="装配前三步原料成整棵 PostCard 成品，作为唯一成品出口",
        enter_line="汇总官接单啦，开始组装成品",
        artifacts_schema="postcard",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=PostCard,
    ),
}

