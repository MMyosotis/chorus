"""Markdown 产出解析:注释元信息抽取 + 四角色正文解析成 artifacts dict。"""
from __future__ import annotations

import re
from typing import Any

_META_RE = re.compile(r"<!--\s*chorus:(\w+)\s*=\s*(.*?)\s*-->")


def parse_meta(content: str) -> dict[str, str]:
    """抽取 chorus 注释元信息,key 小写。"""
    return {m.group(1).lower(): m.group(2) for m in _META_RE.finditer(content)}


def strip_markdown_meta(content: str) -> str:
    """去掉 chorus 注释行,保留其余(含空行结构)。"""
    lines = [ln for ln in content.splitlines() if not _META_RE.match(ln.strip())]
    return "\n".join(lines)


def parse_script_md(body: str) -> list[dict[str, str]]:
    """文案 markdown 解析:heading/paragraph/list/quote 四种 block。"""
    if not body.strip():
        return []
    blocks: list[dict[str, str]] = []
    lines = body.splitlines()
    pending_list: list[str] = []
    pending_para: list[str] = []

    def flush_list():
        if pending_list:
            blocks.append({"kind": "list", "text": "\n".join(pending_list)})
            pending_list.clear()

    def flush_para():
        if pending_para:
            blocks.append({"kind": "paragraph", "text": " ".join(pending_para)})
            pending_para.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush_list(); flush_para()
            blocks.append({"kind": "heading", "text": stripped[3:].strip()})
        elif stripped.startswith("> "):
            flush_list(); flush_para()
            blocks.append({"kind": "quote", "text": stripped[2:].strip()})
        elif stripped.startswith("- "):
            flush_para()
            pending_list.append(stripped[2:].strip())
        elif stripped == "":
            flush_list(); flush_para()
        else:
            flush_list()
            pending_para.append(stripped)
    flush_list(); flush_para()
    return blocks


def parse_idea_md(body: str) -> dict[str, Any]:
    """选题 markdown:### 分候选,视角/理由抽字段。"""
    candidates: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            if current is not None:
                candidates.append(current)
            current = {"index": len(candidates), "title": stripped[4:].strip(), "angle": "", "reason": ""}
        elif current is not None and stripped.startswith("- 视角："):
            current["angle"] = stripped.replace("- 视角：", "").strip()
        elif current is not None and stripped.startswith("- 理由："):
            current["reason"] = stripped.replace("- 理由：", "").strip()
    if current is not None:
        candidates.append(current)
    return {"candidates": candidates, "selected": None}


def parse_image_md(body: str) -> dict[str, Any]:
    """配图 markdown:### 图 N 分组,caption 抽图注,url 留空由 subagent 填。"""
    images: list[dict[str, str]] = []
    caption = ""
    in_group = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            if in_group:
                images.append({"url": "", "caption": caption})
            in_group = True
            caption = ""
        elif in_group and stripped.startswith("caption："):
            caption = stripped.replace("caption：", "").strip()
    if in_group:
        images.append({"url": "", "caption": caption})
    return {"images": images}


def parse_postcard_md(body: str) -> dict[str, Any]:
    """汇总 markdown:# title,## heading,> quote,- list,![] image,#标签 tags。"""
    title = ""
    sections: list[dict[str, Any]] = []
    tags: list[str] = []
    pending_list: list[str] = []
    pending_para: list[str] = []

    def flush_list():
        if pending_list:
            sections.append({"kind": "list", "text": "\n".join(pending_list)})
            pending_list.clear()

    def flush_para():
        if pending_para:
            sections.append({"kind": "paragraph", "text": " ".join(pending_para)})
            pending_para.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not title:
            flush_list(); flush_para()
            title = stripped[2:].strip()
        elif stripped.startswith("## "):
            flush_list(); flush_para()
            sections.append({"kind": "heading", "text": stripped[3:].strip()})
        elif stripped.startswith("> "):
            flush_list(); flush_para()
            sections.append({"kind": "quote", "text": stripped[2:].strip()})
        elif stripped.startswith("- "):
            flush_para()
            pending_list.append(stripped[2:].strip())
        elif stripped.startswith("![") and "](" in stripped:
            flush_list(); flush_para()
            sections.append({"kind": "image", "text": "", "image": {"url": "", "caption": ""}})
        elif stripped.startswith("#标签："):
            flush_list(); flush_para()
            tags = [tag.strip() for tag in stripped.replace("#标签：", "").split() if tag.strip()]
        elif stripped == "":
            flush_list(); flush_para()
        else:
            flush_list()
            pending_para.append(stripped)
    flush_list(); flush_para()
    return {"title": title, "sections": sections, "cover": None, "tags": tags, "summary": ""}
