"""聚合会话领域数据，生成前端直接渲染的视图。"""

from __future__ import annotations

from chorus.domain.intent import IntentConfirmation, IntentState
from chorus.domain.message import MessageView
from chorus.domain.option import OptionPrompt
from chorus.domain.session.bubbles import anchor_ids, build_bubbles
from chorus.domain.session.cards import insert_anchored_card, plan_cards
from chorus.domain.session.recaps import (
    dump_confirmation,
    dump_prompt,
    fold_confirmation_recaps,
    fold_option_recaps,
)
from chorus.domain.session.stage import derive_stage
from chorus.domain.task.graph import TaskGraph, dump_task_graph
from chorus.domain.task.products import DeliveredProduct


def build_session_view(
    messages: list[MessageView],
    graph: TaskGraph,
    products: list[DeliveredProduct],
    intent_state: IntentState,
    confirmations: list[IntentConfirmation],
    prompts: list[OptionPrompt],
    *,
    needs_resume: bool,
) -> dict:
    """聚合成前端一次渲染所需的全部结构，纯函数不碰库。"""

    # 先把任务图转换成前端结构，并记录任务卡对应的消息锚点。
    graph_dump = dump_task_graph(graph)
    plan_anchors = {node.message_id for node in graph.nodes if node.message_id is not None}
    suspended_anchors = anchor_ids(confirmations) | anchor_ids(prompts)

    # 先按对话顺序合并消息，再把任务卡和成品卡插回对应位置。
    entries = build_bubbles(messages, suspended_anchors, plan_anchors)
    for card in plan_cards(graph, products):
        insert_anchored_card(entries, card)

    # 已回答的确认和选项折叠进原助手气泡，供前端回看。
    fold_confirmation_recaps(entries, confirmations)
    fold_option_recaps(entries, prompts)

    # 开放门禁单独返回，阶段文案由当前门禁和任务状态共同派生。
    open_confirmation = next((item for item in confirmations if item.status == "open"), None)
    open_prompt = next((item for item in prompts if item.status == "open"), None)

    return {
        "bubbles": [entry.model_dump(mode="json") for entry in entries],
        "graph": graph_dump,
        "intent_state": intent_state.model_dump(mode="json"),
        "open_confirmation": dump_confirmation(open_confirmation) if open_confirmation else None,
        "open_option_prompt": dump_prompt(open_prompt) if open_prompt else None,
        "stage": derive_stage(graph.nodes, open_confirmation, open_prompt),
        "needs_resume": needs_resume,
    }
