"""Markdown 产出解析:抽取注释元信息,四角色正文解析成产物字典。"""
from __future__ import annotations

import re
from typing import Any

_META_RE = re.compile(r"<!--\s*chorus:(\w+)\s*=\s*(.*?)\s*-->")


def parse_meta(content: str) -> dict[str, str]:
    """抽取项目元信息注释,键名小写。"""
    return {m.group(1).lower(): m.group(2) for m in _META_RE.finditer(content)}


def strip_markdown_meta(content: str) -> str:
    """去掉项目元信息注释行,保留其余(含空行结构)。"""
    lines = [ln for ln in content.splitlines() if not _META_RE.match(ln.strip())]
    return "\n".join(lines)


class BlockCollector:
    """逐行收块:列表与段落双缓冲,块边界处一齐收口。"""

    def __init__(self):
        self.blocks: list[dict[str, Any]] = []
        self._pending_list: list[str] = []
        self._pending_para: list[str] = []

    def flush_list(self) -> None:
        if self._pending_list:
            self.blocks.append({"kind": "list", "text": "\n".join(self._pending_list)})
            self._pending_list.clear()

    def flush_para(self) -> None:
        if self._pending_para:
            self.blocks.append({"kind": "paragraph", "text": " ".join(self._pending_para)})
            self._pending_para.clear()

    def flush_all(self) -> None:
        self.flush_list()
        self.flush_para()

    def add_list_item(self, text: str) -> None:
        self._pending_list.append(text)

    def add_para_line(self, text: str) -> None:
        self._pending_para.append(text)

    def add(self, block: dict[str, Any]) -> None:
        self.blocks.append(block)

    def handle_block_line(self, stripped: str) -> None:
        """处理小标题/引用/列表/空行/段落五种通用行。"""
        if stripped.startswith("## "):
            self.flush_all()
            self.add({"kind": "heading", "text": stripped[3:].strip()})
        elif stripped.startswith("> "):
            self.flush_all()
            self.add({"kind": "quote", "text": stripped[2:].strip()})
        elif stripped.startswith("- "):
            self.flush_para()
            self.add_list_item(stripped[2:].strip())
        elif stripped == "":
            self.flush_all()
        else:
            self.flush_list()
            self.add_para_line(stripped)


def parse_script_md(body: str) -> dict[str, Any]:
    """文案解析:标题/段落/列表/引用四种块。"""
    collector = BlockCollector()
    for line in body.splitlines():
        collector.handle_block_line(line.strip())
    collector.flush_all()
    return {"blocks": collector.blocks}


def parse_idea_md(body: str) -> dict[str, Any]:
    """选题按三级标题分候选,抽视角与理由。"""
    candidates: list[dict[str, Any]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            candidates.append({"index": len(candidates), "title": stripped[4:].strip(), "angle": "", "reason": ""})
        elif candidates:
            normalized = stripped.removeprefix("- ").replace("**", "")
            if normalized.startswith(("视角：", "视角:")):
                candidates[-1]["angle"] = normalized.split(":" if "：" not in normalized else "：", 1)[1].strip()
            elif normalized.startswith(("理由：", "理由:")):
                candidates[-1]["reason"] = normalized.split(":" if "：" not in normalized else "：", 1)[1].strip()
    return {"candidates": candidates, "selected": None}


def parse_image_md(body: str) -> dict[str, Any]:
    """配图按图分组,抽图注,链接留空待子 Agent 填。"""
    images: list[dict[str, str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            images.append({"url": "", "caption": ""})
        elif images and stripped.startswith("caption："):
            images[-1]["caption"] = stripped.replace("caption：", "").strip()
    return {"images": images}


def _handle_postcard_line(
    collector: BlockCollector, stripped: str, title: str, tags: list[str]
) -> tuple[str, list[str]]:
    """处理单行:先大标题/配图/标签特有分支,未命中走通用收块。"""
    if stripped.startswith("# ") and not title:
        collector.flush_all()
        return stripped[2:].strip(), tags
    if stripped.startswith("![") and "](" in stripped:
        collector.flush_all()
        collector.add({"kind": "image", "text": "", "image": {"url": "", "caption": ""}})
        return title, tags
    if stripped.startswith("#标签："):
        collector.flush_all()
        new_tags = [tag.strip() for tag in stripped.replace("#标签：", "").split() if tag.strip()]
        return title, new_tags
    collector.handle_block_line(stripped)
    return title, tags


def parse_postcard_md(body: str) -> dict[str, Any]:
    """汇总:大标题/小标题/引用/列表/配图/标签。"""
    title = ""
    tags: list[str] = []
    collector = BlockCollector()
    for line in body.splitlines():
        title, tags = _handle_postcard_line(collector, line.strip(), title, tags)
    collector.flush_all()
    return {"title": title, "sections": collector.blocks, "cover": None, "tags": tags, "summary": ""}


class UnitCounter:
    """流式数行标记出现次数,容忍跨分片拼接。"""

    def __init__(self, marker: str):
        self._marker = marker
        self._buf = ""
        self._count = 0

    def feed(self, text: str) -> None:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip().startswith(self._marker):
                self._count += 1

    @property
    def count(self) -> int:
        pending = 1 if self._buf.strip().startswith(self._marker) else 0
        return self._count + pending
