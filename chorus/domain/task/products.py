"""已交付成品的筛选、组装与清单文本规则。"""
from __future__ import annotations

from typing import Iterable, Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.artifacts import PostCard
from chorus.domain.task.models import Task


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class DeliveredProduct:
    """已交付成品的对外数据。"""

    id: str
    message_id: Optional[str]
    title: str
    markdown: str
    created_at: float


def select_delivered_tasks(tasks: Iterable[Task]) -> list[Task]:
    """筛出可作为已交付成品的任务。"""
    return [task for task in tasks if task.is_delivered()]


def build_delivered_products(pairs: list[tuple[Task, PostCard]]) -> list[DeliveredProduct]:
    """把已筛好的任务与成品卡按创建时间组装为清单。"""
    ordered = sorted(pairs, key=lambda pair: pair[0].created_at)
    return [DeliveredProduct(
        id=task.id,
        message_id=task.message_id,
        title=card.meta.title,
        markdown=card.markdown,
        created_at=task.created_at,
    ) for task, card in ordered]


def format_product_list(products: list[DeliveredProduct]) -> str:
    """把成品列表格式化为模型可填写的底稿选项。"""
    if not products:
        return "（本会话暂无已交付成品，全新创作请留空底稿标识）"
    return "\n".join(
        f"- {product.id} 《{product.title}》" if product.title else f"- {product.id}"
        for product in products
    )


CANCELLED_PIPELINE_RECEIPT = "创作流水线已被用户放弃，本次未交付成品"


def render_delivery_receipt(task_id: str, card: PostCard) -> str:
    """把已交付成品组装成喂给模型的收口回执。"""
    return (
        f"创作流水线已收口，成品标识={task_id}（标题：{card.meta.title}），"
        "成品全文已交付用户，内容如下：\n\n" + card.markdown
    )
