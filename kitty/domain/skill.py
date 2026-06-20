"""Skill：模型 + 摘要格式化纯操作。

- SkillSummary：注入 system prompt 的摘要。
- SkillContent：load_skill 工具返回的完整内容，from_markdown 解析 frontmatter。
- format_skill_hints：把 SkillSummary 列表拼成 system prompt 的技能摘要段（无技能返回空串）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SkillSummary(BaseModel):
    """注入 system prompt 的摘要。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str


class SkillContent(BaseModel):
    """load_skill 工具返回的完整内容。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    full_content: str

    @classmethod
    def from_markdown(cls, text: str, fallback_name: str) -> "SkillContent":
        """从 skill markdown 文本构造：解析 frontmatter（name/description），full_content 为原文。"""
        name = fallback_name
        description = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                name, description = cls._parse_frontmatter(parts[1], fallback_name)
        return cls(name=name, description=description, full_content=text)

    @staticmethod
    def _parse_frontmatter(frontmatter: str, fallback_name: str) -> tuple[str, str]:
        name = fallback_name
        description = ""
        for line in frontmatter.strip().splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if key == "name":
                name = val
            elif key == "description":
                description = val
        return name, description


def format_skill_hints(summaries: list[SkillSummary]) -> str:
    """生成 skill 摘要文本（作为 PromptContext.skill_hints 的来源），无技能时返回空串。"""
    if not summaries:
        return ""
    lines = ["## 可用技能（使用 load_skill 工具获取完整内容）"]
    for s in summaries:
        lines.append(f"- **{s.name}**: {s.description}")
    return "\n".join(lines)
