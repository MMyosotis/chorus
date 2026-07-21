"""Markdown 产出解析：把 Mistune AST 还原成四角色的产物字典。"""
from __future__ import annotations

import re
from typing import Any, cast

import mistune
from mistune.renderers.markdown import MarkdownRenderer

from chorus.domain.task.errors import AbandonError, ValidationError


Token = dict[str, Any]

_IMAGE_TITLE_RE = re.compile(r"图 \d+")
_PREVIEW_REF_RE = re.compile(r"<!--\s*preview_ref\s*:\s*([^/\s]+/\S+?)\s*-->")
_STYLESHEET_REF_RE = re.compile(r"<!--\s*stylesheet_ref\s*:\s*([^/\s]+/\S+?)\s*-->")
# 失败块：模型主动声明本步放弃，正文为失败说明
_ABANDON_RE = re.compile(r"^\s*#\s*失败\s*\n+(?P<reason>.+?)\s*$", re.DOTALL)


def _detect_abandon(body: str) -> str | None:
    """命中失败块则返回失败说明，否则 None。失败块优先于结构解析。"""
    match = _ABANDON_RE.match(body)
    return match.group("reason") if match else None


def _parse_markdown(body: str) -> list[Token]:
    """用 Mistune 把正文解析成去除空行节点的 AST。"""
    tokens = cast(list[Token], mistune.markdown(body, renderer="ast", plugins=("table",)))
    return [token for token in tokens if token["type"] != "blank_line"]


def _render_inline(tokens: list[Token]) -> str:
    """把行内 AST 还原为前端可继续渲染的 Markdown。"""
    return MarkdownRenderer().render_tokens(tokens, mistune.BlockState())


def _parse_list_items(token: Token) -> list[str]:
    """把无序列表 AST 还原成文本项。"""
    attrs = token.get("attrs", {})
    if attrs.get("ordered"):
        raise ValidationError("不支持有序列表", "请改用 - 开头的无序列表")
    return [_parse_list_item(item) for item in token.get("children", [])]


def _parse_list_item(token: Token) -> str:
    """还原一个单层列表项。"""
    children = token.get("children", [])
    valid = len(children) == 1 and children[0]["type"] in {"block_text", "paragraph"}
    if not valid:
        raise ValidationError("列表结构过于复杂", "请使用单层无序列表，每项只写一行文字")
    return _render_inline(children[0].get("children", []))


def _parse_table(token: Token) -> dict[str, Any]:
    """把 Mistune 表格 AST 还原成成品表格。"""
    children = token.get("children", [])
    valid = children and children[0]["type"] == "table_head"
    if not valid:
        raise ValidationError("表格结构错误", "表格必须包含表头和分隔行")
    headers = [_render_inline(cell.get("children", [])) for cell in children[0].get("children", [])]
    body = children[1].get("children", []) if len(children) > 1 else []
    rows = [_parse_table_row(row) for row in body]
    return {"headers": headers, "rows": rows}


def _parse_table_row(token: Token) -> list[str]:
    """还原一行表格单元。"""
    return [_render_inline(cell.get("children", [])) for cell in token.get("children", [])]


def _parse_section(token: Token) -> dict[str, Any]:
    """把一个块级 AST 节点还原成正文节点。"""
    kind = token["type"]
    if kind == "heading":
        if token["attrs"]["level"] != 2:
            raise ValidationError("正文标题级别错误", "正文小标题统一使用 ##")
        return {"kind": "heading", "text": _render_inline(token.get("children", []))}
    if kind == "paragraph":
        children = token.get("children", [])
        if len(children) == 1 and children[0]["type"] == "image":
            return _parse_image_section(children[0])
        return {"kind": "paragraph", "text": _render_inline(children)}
    if kind == "block_quote":
        return {"kind": "quote", "text": _parse_quote(token)}
    if kind == "list":
        return {"kind": "list", "text": "\n".join(_parse_list_items(token))}
    if kind == "table":
        return {"kind": "table", "text": "", "table": _parse_table(token)}
    if kind == "thematic_break":
        return {"kind": "divider", "text": ""}
    raise ValidationError(f"不支持的 Markdown 块：{kind}", "请严格使用系统提示允许的 Markdown 结构")


def _parse_image_section(token: Token) -> dict[str, Any]:
    """把图片 AST 还原成成品图片节点。"""
    return {
        "kind": "image",
        "text": "",
        "image": {
            "url": token["attrs"]["url"],
            "caption": _render_inline(token.get("children", [])),
        },
    }


def _parse_quote(token: Token) -> str:
    """还原一个单段引用。"""
    children = token.get("children", [])
    if len(children) != 1 or children[0]["type"] != "paragraph":
        raise ValidationError("引用结构过于复杂", "每个引用只写一个段落")
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


def _parse_image_item(heading: Token, details: Token) -> dict[str, str]:
    """把三级标题和详情段落还原成配图。"""
    title = _render_inline(heading.get("children", [])) if heading["type"] == "heading" else ""
    valid_heading = heading["type"] == "heading" and heading["attrs"]["level"] == 3
    if not valid_heading or not _IMAGE_TITLE_RE.fullmatch(title) or details["type"] != "paragraph":
        raise ValidationError("配图格式错误", "每张图使用 ### 图 N，后跟 url：和 caption：两行")
    lines = _render_inline(details.get("children", [])).splitlines()
    valid_details = len(lines) == 2 and lines[0].startswith("url：") and lines[1].startswith("caption：")
    if not valid_details:
        raise ValidationError("配图字段格式错误", "每张图只保留 url：和 caption：两行")
    image = {
        "url": lines[0].removeprefix("url：").strip(),
        "caption": lines[1].removeprefix("caption：").strip(),
    }
    if not image["caption"]:
        raise ValidationError("配图图注为空", "caption：必须填写，生图失败时只留空 url：")
    return image


def _pair_tokens(tokens: list[Token], correction: str) -> list[tuple[Token, Token]]:
    """把角色产物 AST 按标题与详情两节点分组。"""
    if not tokens or len(tokens) % 2:
        raise ValidationError("Markdown 产物分组错误", correction)
    return list(zip(tokens[::2], tokens[1::2]))


def _parse_postcard_title(token: Token) -> str:
    """解析成品首节点的大标题。"""
    valid = token["type"] == "heading" and token["attrs"]["level"] == 1
    title = _render_inline(token.get("children", [])) if valid else ""
    if not title:
        raise ValidationError("成品标题格式错误", "资源引用后的第一个块必须是非空 # 大标题")
    return title


def _parse_postcard_tags(token: Token) -> list[str]:
    """解析成品末节点的标签行。"""
    text = _render_inline(token.get("children", [])) if token["type"] == "paragraph" else ""
    if not text.startswith("#标签："):
        raise ValidationError("成品标签格式错误", "最后一个块必须使用 #标签：#话题1 #话题2 格式")
    tags = text.removeprefix("#标签：").split()
    if not tags or any(not tag.startswith("#") for tag in tags):
        raise ValidationError("成品标签格式错误", "使用 #标签：#话题1 #话题2 格式")
    return tags


def parse_script_md(body: str) -> dict[str, Any]:
    """解析文案官的标题、段落、列表与引用。"""
    if (reason := _detect_abandon(body)) is not None:
        raise AbandonError(reason)
    blocks = [_parse_section(token) for token in _parse_markdown(body)]
    if not blocks:
        raise ValidationError("文案正文为空", "请按 Markdown 协议输出完整文案")
    return {"blocks": blocks}


def parse_idea_md(body: str) -> dict[str, Any]:
    """解析选题官按三级标题分组的候选。"""
    if (reason := _detect_abandon(body)) is not None:
        raise AbandonError(reason)
    pairs = _pair_tokens(_parse_markdown(body), "每个候选使用 ### 标题，后跟视角和理由列表")
    candidates = [_parse_idea_candidate(index, *pair) for index, pair in enumerate(pairs)]
    return {"candidates": candidates, "selected": None}


def parse_image_md(body: str) -> dict[str, Any]:
    """解析配图官按三级标题分组的图片。"""
    if (reason := _detect_abandon(body)) is not None:
        raise AbandonError(reason)
    pairs = _pair_tokens(_parse_markdown(body), "每张图使用 ### 图 N，后跟 url：和 caption：两行")
    return {"images": [_parse_image_item(*pair) for pair in pairs]}


def parse_postcard_md(body: str) -> dict[str, Any]:
    """解析汇总官的成品标题、正文、图片、标签与资源引用。"""
    if (reason := _detect_abandon(body)) is not None:
        raise AbandonError(reason)
    lines = body.splitlines()
    preview = _PREVIEW_REF_RE.fullmatch(lines[0].strip()) if len(lines) >= 1 else None
    stylesheet = _STYLESHEET_REF_RE.fullmatch(lines[1].strip()) if len(lines) >= 2 else None
    if not preview or not stylesheet:
        raise ValidationError("资源引用格式错误", "第一行写 preview_ref，第二行写 stylesheet_ref，路径格式为 技能名/包内路径")

    tokens = _parse_markdown("\n".join(lines[2:]))
    if len(tokens) < 3:
        raise ValidationError("汇总成品不完整", "成品必须包含 # 大标题、正文块与 #标签：行")
    return {
        "title": _parse_postcard_title(tokens[0]),
        "sections": [_parse_section(token) for token in tokens[1:-1]],
        "cover": None,
        "tags": _parse_postcard_tags(tokens[-1]),
        "summary": "",
        "meta": {"preview_ref": preview.group(1), "stylesheet_ref": stylesheet.group(1)},
    }
