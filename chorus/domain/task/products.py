"""已交付成品的筛选、组装与清单文本规则。"""
from __future__ import annotations

from typing import Iterable, Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydataclass

from chorus.domain.task.artifacts import PostCard
from chorus.domain.task.models import Task


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class ProductCandidate:
    """成品列表的领域输入：任务行与对应成品卡。"""

    task: Task
    card: PostCard

    def to_delivered_product(self) -> DeliveredProduct:
        """把候选转换为成品列表项。"""
        return DeliveredProduct(
            id=self.task.id,
            message_id=self.task.message_id,
            title=self.card.meta.get("title", ""),
            markdown=self.card.markdown,
            created_at=self.task.created_at,
        )


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


def list_products(candidates: list[ProductCandidate]) -> list[DeliveredProduct]:
    """把已筛好的成品候选按创建时间组装为清单。"""
    ordered = sorted(candidates, key=lambda candidate: candidate.task.created_at)
    return [candidate.to_delivered_product() for candidate in ordered]


def format_product_list(products: list[DeliveredProduct]) -> str:
    """把成品列表格式化为模型可填写的底稿选项。"""
    if not products:
        return "（本会话暂无已交付成品，全新创作请留空底稿标识）"
    return "\n".join(
        f"- {product.id} 《{product.title}》" if product.title else f"- {product.id}"
        for product in products
    )
