"""角色档案注册表：四子角色的展示名、职责、入场台词、产物模型与产物解析。
新增角色只需加一条档案，文案禁 emoji，切段校验还原随档案内聚。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type

from pydantic import ValidationError as PydValidationError

from chorus.domain.task.artifacts import (
    IdeaArtifacts,
    ImageArtifacts,
    Narrative,
    PostCard,
    ScriptArtifacts,
)
from chorus.domain.task.errors import ValidationError
from chorus.domain.task.markdown import (
    parse_idea_md,
    parse_image_md,
    parse_meta,
    parse_postcard_md,
    parse_script_md,
    strip_markdown_meta,
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
    composing_label: str

    def build_artifacts(self, raw: Any) -> Any:
        """把原始数据按本角色的产物形状还原成对象。"""
        return self.artifacts_model(**raw)

    def parse_output(self, content: str) -> tuple[Any, Narrative]:
        """抽注释元信息与 markdown 正文，按角色解析校验。"""
        meta = parse_meta(content)
        if "awaiting" not in meta or "done" not in meta:
            raise ValidationError(
                "缺话术注释",
                "请用 <!-- chorus:awaiting=... --> 和 <!-- chorus:done=... --> 注释给出话术",
            )
        body = strip_markdown_meta(content)
        artifacts = self._parse_artifacts_md(body)
        narrative = self._validate_narrative(meta["awaiting"], meta["done"])
        return artifacts, narrative

    def _parse_artifacts_md(self, body: str) -> Any:
        """按角色调对应 markdown 解析，再按本角色模型构造校验。"""
        raw = _MD_PARSERS[self.artifacts_schema](body)
        if self.artifacts_schema == "script":
            raw = {"blocks": raw}
        return self._validate_artifacts(raw)

    def _validate_artifacts(self, artifacts: Any) -> Any:
        """用本角色模型构造即校验，失败转异常并附修正提示。"""
        try:
            return self.build_artifacts(artifacts)
        except PydValidationError as e:
            raise ValidationError(
                f"ARTIFACTS 校验失败: {e}",
                f"{self.display_name}产物须符合 {self.artifacts_model.__name__} 结构",
            ) from e

    def _validate_narrative(self, awaiting: str, done: str) -> Narrative:
        """构造即校验，失败转异常并附修正提示。"""
        try:
            return Narrative(awaiting_line=awaiting, done_line=done)
        except PydValidationError as e:
            raise ValidationError(
                f"话术校验失败: {e}",
                "话术须为 awaiting_line/done_line 字符串",
            ) from e


AGENT_PROFILES: dict[str, AgentProfile] = {
    "idea": AgentProfile(
        agent_type="idea",
        display_name="选题官",
        role_desc="调研热点、琢磨选题，给出多个候选标题与切入角度",
        enter_line="选题官接单啦，先去翻翻最近的热点",
        artifacts_schema="idea",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=IdeaArtifacts,
        composing_label="个候选",
    ),
    "script": AgentProfile(
        agent_type="script",
        display_name="文案官",
        role_desc="依据选题撰写图文博文正文，拆成有序块草稿",
        enter_line="文案官接单啦，开始码字",
        artifacts_schema="script",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=ScriptArtifacts,
        composing_label="段",
    ),
    "image": AgentProfile(
        agent_type="image",
        display_name="配图官",
        role_desc="为博文生成配图，给出图片列表与图注",
        enter_line="配图官接单啦，准备出图",
        artifacts_schema="image",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=ImageArtifacts,
        composing_label="张",
    ),
    "finalize": AgentProfile(
        agent_type="finalize",
        display_name="汇总官",
        role_desc="装配前三步原料成整棵 PostCard 成品，作为唯一成品出口",
        enter_line="汇总官接单啦，开始组装成品",
        artifacts_schema="postcard",
        expected_sections=("artifacts", "narrative"),
        artifacts_model=PostCard,
        composing_label="节",
    ),
}


_MD_PARSERS = {
    "idea": parse_idea_md,
    "script": parse_script_md,
    "image": parse_image_md,
    "postcard": parse_postcard_md,
}
