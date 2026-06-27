"""Skill 领域模型。

SkillSummary：注入 system prompt 的摘要。
SkillContent：load_skill 工具返回的完整内容，from_markdown 解析 frontmatter。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSummary:
    """注入 system prompt 的摘要。"""

    name: str
    description: str


@dataclass(frozen=True)
class SkillContent:
    """load_skill 工具返回的完整内容。"""

    name: str
    description: str
    full_content: str

    @classmethod
    def from_markdown(cls, text: str, fallback_name: str) -> "SkillContent":
        """从 skill markdown 文本构造：解析 frontmatter（name/description），full_content 为原文。"""
        name, description = fallback_name, ""
        parts = text.split("---", 2) if text.startswith("---") else []
        if len(parts) >= 3:
            name, description = cls._parse_frontmatter(parts[1], fallback_name)
        return cls(name=name, description=description, full_content=text)

    @staticmethod
    def _parse_frontmatter(frontmatter: str, fallback_name: str) -> tuple[str, str]:
        values = {"name": fallback_name, "description": ""}
        for line in frontmatter.strip().splitlines():
            key, val = SkillContent._split_kv(line)
            values[key] = val
        return values["name"], values["description"]

    @staticmethod
    def _split_kv(line: str) -> tuple[str, str]:
        """按第一个冒号拆 key/value 并去空白；无冒号时 key 为整行、val 为空。"""
        key, _, val = line.partition(":")
        return key.strip(), val.strip()
