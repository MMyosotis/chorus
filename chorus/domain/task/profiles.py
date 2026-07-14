"""角色档案注册表：四子角色的展示名、职责、入场台词、产物模型与产物解析。
新增角色只需加一条档案，文案禁 emoji，切段校验还原随档案内聚。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Type

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
    artifacts_schema: str
    artifacts_model: Type[Any]
    artifacts_parser: Callable[[str], Any]
    composing_label: str
    activity_lines: dict = field(default_factory=dict)

    def activity_line(self, kind: str) -> str:
        """按活动态取本角色台词，未声明则空。"""
        return self.activity_lines.get(kind, "")

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
        """按角色调对应 markdown 解析,再按本角色模型构造校验。"""
        raw = self.artifacts_parser(body)
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
        artifacts_schema="idea",
        artifacts_model=IdeaArtifacts,
        artifacts_parser=parse_idea_md,
        composing_label="个候选",
        activity_lines={
            "thinking": "先翻翻最近的热点",
            "searching": "翻翻热点",
            "composing": "笔尖正在落纸",
        },
    ),
    "script": AgentProfile(
        agent_type="script",
        display_name="文案官",
        role_desc="依据选题撰写图文博文正文，拆成有序块草稿",
        artifacts_schema="script",
        artifacts_model=ScriptArtifacts,
        artifacts_parser=parse_script_md,
        composing_label="段",
        activity_lines={
            "thinking": "先在脑子里理一理",
            "searching": "查查资料",
            "composing": "笔尖正在落纸",
        },
    ),
    "image": AgentProfile(
        agent_type="image",
        display_name="配图官",
        role_desc="为博文生成配图，给出图片列表与图注",
        artifacts_schema="image",
        artifacts_model=ImageArtifacts,
        artifacts_parser=parse_image_md,
        composing_label="张",
        activity_lines={
            "thinking": "先在脑子里画一画",
            "drawing": "作画",
            "composing": "笔尖正在落纸",
        },
    ),
    "finalize": AgentProfile(
        agent_type="finalize",
        display_name="汇总官",
        role_desc="装配前三步原料成整棵 PostCard 成品，作为唯一成品出口",
        artifacts_schema="postcard",
        artifacts_model=PostCard,
        artifacts_parser=parse_postcard_md,
        composing_label="节",
        activity_lines={
            "thinking": "先在脑子里理一理结构",
            "composing": "笔尖正在落纸",
        },
    ),
}
