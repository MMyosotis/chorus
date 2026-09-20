"""把任务图和成品投影成对话区卡片。"""

from __future__ import annotations

from typing import Optional, Union

from chorus.domain.session.bubbles import find_bubble
from chorus.domain.session.entries import (
    AssistantBubble,
    BubbleEntry,
    ProductCard,
    TaskCard,
    TaskCardKind,
)
from chorus.domain.task.graph import (
    TaskGraph,
    TaskNodeView,
    build_task_node_response,
)
from chorus.domain.task.models import AgentType, TaskStatus
from chorus.domain.task.products import DeliveredProduct


def plan_cards(graph: TaskGraph, products: list[DeliveredProduct]) -> list[Union[TaskCard, ProductCard]]:
    """任务图快照与成品清单投影成对话区卡片，顺序即插入顺序。"""
    return [
        *_confirmed_task_cards(graph.nodes),
        *_running_task_cards(graph.nodes),
        *_hil_task_cards(graph.nodes),
        *_recovery_task_cards(graph.nodes),
        *_product_cards(products),
    ]


def _confirmed_task_cards(nodes: list[TaskNodeView]) -> list[TaskCard]:
    return [
        _task_card("confirmed", node)
        for node in nodes
        if node.status == TaskStatus.FINISHED and node.agent_type != AgentType.FINALIZE
    ]


def _running_task_cards(nodes: list[TaskNodeView]) -> list[TaskCard]:
    running = next((node for node in nodes if node.status == TaskStatus.RUNNING), None)
    return [_task_card("running", running)] if running is not None else []


def _hil_task_cards(nodes: list[TaskNodeView]) -> list[TaskCard]:
    return [
        _task_card("hil", node)
        for node in nodes
        if node.status == TaskStatus.AWAITING_CONFIRM
    ]


def _recovery_task_cards(nodes: list[TaskNodeView]) -> list[TaskCard]:
    return [
        _task_card("recovery", node)
        for node in nodes
        if node.status == TaskStatus.FAILED
    ]


def _product_cards(products: list[DeliveredProduct]) -> list[ProductCard]:
    return [
        ProductCard(id=f"product:{product.id}", product=product, anchor_message_id=product.message_id)
        for product in products
        if product.message_id is not None
    ]


def _task_card(kind: TaskCardKind, task: TaskNodeView) -> TaskCard:
    return TaskCard(
        kind=kind,
        id=f"{kind}:{task.id}",
        task=build_task_node_response(task),
        anchor_message_id=task.message_id,
    )


def insert_anchored_card(entries: list[BubbleEntry], card: Union[TaskCard, ProductCard]) -> None:
    """卡片插到锚点气泡之后，同锚卡片按投影顺序排列。"""
    anchor_message_id = card.anchor_message_id
    if anchor_message_id is None:
        return
    found = find_bubble(entries, anchor_message_id)
    if found is None:
        return
    insert_index = _find_card_insert_index(entries, found[0], anchor_message_id)
    entries.insert(insert_index, card)


def _find_card_insert_index(entries: list[BubbleEntry], bubble_index: int, anchor_message_id: str) -> int:
    insert_index = bubble_index + 1
    while insert_index < len(entries) and _is_same_anchor_card(entries[insert_index], anchor_message_id):
        insert_index += 1
    return insert_index


def _is_same_anchor_card(entry: BubbleEntry, anchor_message_id: str) -> bool:
    return (
        isinstance(entry, (TaskCard, ProductCard))
        and entry.anchor_message_id == anchor_message_id
    )
