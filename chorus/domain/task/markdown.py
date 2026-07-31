"""Markdown 产出解析：把 Mistune AST 还原成四角色的产物字典。"""
from __future__ import annotations

import re
from functools import wraps
from typing import Any, cast

import mistune
from mistune.renderers.markdown import MarkdownRenderer

from chorus.domain.task.errors import AbandonError, ValidationError


Token = dict[str, Any]

# 失败块：模型主动声明本步放弃，分隔后为失败说明
_ABANDON_RE = re.compile(r"^\s*#\s*失败[\s:：]+(?P<reason>.+)\s*$", re.DOTALL)


def _detect_abandon(body: str) -> str | None:
    """命中失败块则返回失败说明，否则 None。失败块优先于结构解析。"""
    match = _ABANDON_RE.match(body)
    return match.group("reason") if match else None


def _abandon_aware(parser):
    """先判失败块再走结构解析，统一放弃通道。"""
    @wraps(parser)
    def _parse(body: str) -> dict[str, Any]:
        if (reason := _detect_abandon(body)) is not None:
            raise AbandonError(reason)
        return parser(body)
    return _parse


def _parse_markdown(body: str) -> list[Token]:
    """用 Mistune 把正文解析成去除空行节点的 AST。"""
    tokens = cast(list[Token], mistune.markdown(body, renderer="ast", plugins=("table",)))
    return [token for token in tokens if token["type"] != "blank_line"]


def _render_inline(tokens: list[Token]) -> str:
    """把行内 AST 还原为前端可继续渲染的 Markdown。"""
    return MarkdownRenderer().render_tokens(tokens, mistune.BlockState())


def _parse_list_items(token: Token) -> list[str]:
    """把列表 AST 还原成文本项。"""
    return [_parse_list_item(item) for item in token.get("children", [])]


def _parse_list_item(token: Token) -> str:
    """还原一个单层列表项。"""
    children = token.get("children", [])
    valid = len(children) == 1 and children[0]["type"] in {"block_text", "paragraph"}
    if not valid:
        raise ValidationError("列表结构过于复杂", "请使用单层无序列表，每项只写一行文字")
    return _render_inline(children[0].get("children", []))


def _parse_idea_candidate(index: int, heading: Token, details: Token) -> dict[str, Any]:
    """把三级标题和详情列表还原成选题候选。"""
    valid_heading = heading["type"] == "heading" and heading["attrs"]["level"] == 3
    if not valid_heading or details["type"] != "list":
        raise ValidationError("候选格式错误", "每个候选使用 ### 标题，后跟视角和理由列表")

    items = _parse_list_items(details)
    valid_items = len(items) == 2 and items[0].startswith("视角：") and items[1].startswith("理由：")
    if not valid_items:
        raise ValidationError("候选字段格式错误", "每个候选只保留 - 视角：和 - 理由：两项")

    candidate = {
        "index": index,
        "title": _render_inline(heading.get("children", [])),
        "angle": items[0].removeprefix("视角：").strip(),
        "reason": items[1].removeprefix("理由：").strip(),
    }
    if not all((candidate["title"], candidate["angle"], candidate["reason"])):
        raise ValidationError("候选内容不完整", "每个候选都必须包含非空的标题、视角和理由")
    return candidate


def _extract_images(token: Token) -> list[dict[str, str]]:
    """递归抽取 AST 中的图片节点。"""
    found: list[dict[str, str]] = []
    if token.get("type") == "image":
        found.append({
            "url": token.get("attrs", {}).get("url", ""),
            "caption": _render_inline(token.get("children", [])),
        })
    for child in token.get("children", []):
        found.extend(_extract_images(child))
    return found


def _pair_tokens(tokens: list[Token], correction: str) -> list[tuple[Token, Token]]:
    """把角色产物 AST 按标题与详情两节点分组。"""
    if not tokens or len(tokens) % 2:
        raise ValidationError("Markdown 产物分组错误", correction)
    return list(zip(tokens[::2], tokens[1::2]))


def _split_front_matter(body: str) -> tuple[list[str], str]:
    """分离 front matter 行与正文，无 front matter 则返回空列表与原文。"""
    lines = body.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], body
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return [], body
    return lines[1:end], "\n".join(lines[end + 1:]).lstrip("\n")


def _take_field(lines: list[str], key: str) -> str:
    """从 front matter 行取字段值。"""
    prefix = f"{key}:"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _join_front_matter(remaining: list[str], rest: str) -> str:
    """剩余 front matter 非空则重新包围，否则只返回正文。"""
    if remaining:
        return "---\n" + "\n".join(remaining) + "\n---\n\n" + rest
    return rest


def _first_h1_text(tokens: list[Token]) -> str:
    """取首个一级标题的文本。"""
    for token in tokens:
        if token["type"] == "heading" and token["attrs"]["level"] == 1:
            return _render_inline(token.get("children", []))
    return ""


@_abandon_aware
def parse_script_md(body: str) -> dict[str, Any]:
    """解析文案官的标准 markdown 正文。"""
    tokens = _parse_markdown(body)
    h1_count = sum(1 for token in tokens if token["type"] == "heading" and token["attrs"]["level"] == 1)
    if h1_count != 1:
        raise ValidationError("文案标题格式错误", "正文必须有且仅有一个 # 大标题")
    return {"markdown": body}


@_abandon_aware
def parse_idea_md(body: str) -> dict[str, Any]:
    """解析选题官按三级标题分组的候选。"""
    pairs = _pair_tokens(_parse_markdown(body), "每个候选使用 ### 标题，后跟视角和理由列表")
    candidates = [_parse_idea_candidate(index, *pair) for index, pair in enumerate(pairs)]
    return {"candidates": candidates, "selected": None}


@_abandon_aware
def parse_image_md(body: str) -> dict[str, Any]:
    """解析配图官的标准 markdown 图片。"""
    images: list[dict[str, str]] = []
    for token in _parse_markdown(body):
        images.extend(_extract_images(token))
    if not any(image["url"] for image in images):
        raise ValidationError("配图 url 缺失", "至少一张图填入 generate_image 返回的 url")
    return {"images": images}


@_abandon_aware
def parse_postcard_md(body: str) -> dict[str, Any]:
    """解析汇总官的成品 markdown 与资源引用元数据。"""
    front_lines, rest = _split_front_matter(body)
    preview = _take_field(front_lines, "preview_ref")
    stylesheet = _take_field(front_lines, "stylesheet_ref")
    if not preview or not stylesheet:
        raise ValidationError("资源引用缺失", "front matter 必须含 preview_ref 与 stylesheet_ref")

    remaining = [line for line in front_lines if not line.startswith(("preview_ref:", "stylesheet_ref:"))]
    markdown = _join_front_matter(remaining, rest)
    tokens = _parse_markdown(markdown)
    h1_count = sum(1 for token in tokens if token["type"] == "heading" and token["attrs"]["level"] == 1)
    if h1_count != 1:
        raise ValidationError("成品标题格式错误", "正文必须有且仅有一个 # 大标题")

    title = _first_h1_text(tokens)
    return {
        "markdown": markdown,
        "meta": {"preview_ref": preview, "stylesheet_ref": stylesheet, "title": title},
    }
