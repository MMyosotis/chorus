# kitty/domain/task/post.py
"""成品契约：PostCard 博文卡片树（前端渲染目标）。

finaliz 子 Agent 产出一棵强类型、有界的 PostCard 树，前端 PostCard.vue 拿到即
渲染成小红书/微博式可读卡片。kind 枚举固定有界，前端按 kind 套样式，不猜内容格式。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class PostImage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    caption: str = ""


class PostSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["paragraph", "heading", "list", "quote", "image"]
    text: str = ""  # paragraph/heading/quote 文本; list 用 \n 分条
    image: Optional[PostImage] = None  # kind=image 时必填


class PostCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    cover: Optional[PostImage] = None
    sections: list[PostSection]
    tags: list[str] = []
    summary: str = ""
