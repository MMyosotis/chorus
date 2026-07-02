"""角色档案注册表：四子角色的展示名、职责、入场台词、产物模型与产物解析。

新增角色只需加一条档案。文案纯文本禁 emoji。产物解析（切段→校验→还原）随
档案内聚：每个角色知道自己的产物形状与展示名，parse_output 是 build_artifacts
的兄弟方法。
"""
from __future__ import annotations

import json
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


@dataclass(frozen=True)
class AgentProfile:
    agent_type: str
    display_name: str
    role_desc: str
    enter_line: str
    artifacts_schema: str
    expected_sections: tuple[str, ...]
    artifacts_model: Type[Any]

    def build_artifacts(self, raw: Any) -> Any:
        """把原始数据按本角色的产物形状还原成对象。"""
        return self.artifacts_model(**raw)

    def parse_output(self, content: str) -> tuple[Any, Narrative]:
        """切段、解析、按本角色模型校验。失败抛异常并精确定位缺段或字段错。"""
        sections = parse_sections(content)
        if "artifacts" not in sections:
            raise ValidationError("缺 ARTIFACTS 段", f"请在 <<<ARTIFACTS:json>>>...<<<ARTIFACTS_END>>> 段内输出产物")
        if "narrative" not in sections:
            raise ValidationError("缺 NARRATIVE 段", f"请在 <<<NARRATIVE:json>>>...<<<NARRATIVE_END>>> 段内输出角色话术")
        artifacts = _parse_json(sections["artifacts"], "ARTIFACTS")
        artifacts = self._validate_artifacts(artifacts)
        narrative = _parse_json(sections["narrative"], "NARRATIVE")
        narrative = _validate_narrative(narrative)
        return artifacts, narrative

    def _validate_artifacts(self, artifacts: Any) -> Any:
        """用本角色模型构造即校验，失败转异常并附修正提示。"""
        try:
            return self.build_artifacts(artifacts)
        except PydValidationError as e:
            raise ValidationError(
                f"ARTIFACTS 校验失败: {e}",
                f"{self.display_name}产物须符合 {self.artifacts_model.__name__} 结构",
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


_SECTION_OPEN = "<<<"
_SECTION_CLOSE = ">>>"


def parse_sections(content: str) -> dict[str, str]:
    """按分隔符切段，容忍段外杂文，重复标签后者覆盖。

    段格式：``<<<TAG:fmt>>>正文<<<TAG_END>>>``，``:fmt`` 可省。
    """
    sections: dict[str, str] = {}
    pos = 0
    while pos < len(content):
        open_at = content.find(_SECTION_OPEN, pos)
        if open_at == -1:
            break
        header_close = content.find(_SECTION_CLOSE, open_at)
        if header_close == -1:
            break
        header = content[open_at + len(_SECTION_OPEN):header_close]
        tag = header.split(":", 1)[0]

        end_marker = f"{_SECTION_OPEN}{tag}_END{_SECTION_CLOSE}"
        body_start = header_close + len(_SECTION_CLOSE)
        body_end = content.find(end_marker, body_start)
        if body_end == -1:
            break

        sections[tag.strip().lower()] = content[body_start:body_end].strip()
        pos = body_end + len(end_marker)
    return sections


def _parse_json(raw: str, tag: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"{tag} 段 JSON 解析失败: {e}", f"请把 {tag} 段内容写成合法 JSON") from e


def _validate_narrative(data: Any) -> Narrative:
    """构造即校验，失败转异常并附修正提示。"""
    try:
        return Narrative(**data)
    except PydValidationError as e:
        raise ValidationError(
            f"NARRATIVE 校验失败: {e}",
            "NARRATIVE 须含 awaiting_line/done_line(字符串)",
        ) from e
