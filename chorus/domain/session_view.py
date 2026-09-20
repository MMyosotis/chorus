"""会话视图装配：把消息、任务图、意图与选项留档折成前端直接渲染的成品结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Iterable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.intent import IntentConfirmation, IntentState
from chorus.domain.message import MessageView
from chorus.domain.option import OptionPrompt
from chorus.domain.task.graph import (
    TaskGraph,
    TaskNodeResponse,
    TaskNodeView,
    build_task_node_response,
    dump_task_graph,
)
from chorus.domain.task.products import DeliveredProduct
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.task.models import AgentType, TaskStatus
from chorus.domain.trace import ToolInvocation

_TASK_STATE_LABELS: dict[TaskStatus, str] = {
    TaskStatus.RUNNING: "执行中",
    TaskStatus.AWAITING_CONFIRM: "等待确认",
    TaskStatus.FAILED: "需要处理",
}


class _ViewEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str


class UserEntry(_ViewEntry):
    kind: Literal["user"] = "user"
    role: Literal["user"] = "user"
    content: str


class IntentRecap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    intent_state: dict


class OptionRecap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    option_prompt: dict


Recap = Union[IntentRecap, OptionRecap]


class AssistantBubble(_ViewEntry):
    kind: Literal["assistant"] = "assistant"
    role: Literal["assistant"] = "assistant"
    content: str
    tools: list[ToolInvocation]
    message_ids: list[str]
    recaps: list[Recap]
    suspended: bool


TaskCardKind = Literal["confirmed", "running", "hil", "recovery"]


class TaskCard(_ViewEntry):
    kind: TaskCardKind
    task: TaskNodeResponse
    anchor_message_id: Optional[str]


class ProductCard(_ViewEntry):
    kind: Literal["product"] = "product"
    product: DeliveredProduct
    anchor_message_id: Optional[str]


BubbleEntry = Annotated[
    Union[UserEntry, AssistantBubble, TaskCard, ProductCard],
    Field(discriminator="kind"),
]


@dataclass(frozen=True)
class _AssistantTurn:
    message: MessageView
    has_content: bool
    suspended: bool
    plan_created: bool


@dataclass(frozen=True)
class _BubbleState:
    bubble: AssistantBubble
    plan_created: bool
    entry_index: int


class _BubbleAccumulator:
    """维护会话气泡装配过程的临时状态。"""

    def __init__(self, suspended_anchors: set[str], plan_anchors: set[str]):
        self._suspended_anchors = suspended_anchors
        self._plan_anchors = plan_anchors
        self._entries: list[BubbleEntry] = []
        self._current: Optional[_BubbleState] = None

    @property
    def entries(self) -> list[BubbleEntry]:
        return self._entries

    def consume(self, message: MessageView) -> None:
        if message.role == "assistant":
            self._consume_assistant(message)
            return
        self._consume_user(message)

    def _consume_user(self, message: MessageView) -> None:
        self._entries.append(UserEntry(id=message.id, content=message.content))
        self._current = None

    def _consume_assistant(self, message: MessageView) -> None:
        self._reset_plan_boundary()
        turn = _classify_assistant_turn(message, self._suspended_anchors, self._plan_anchors)
        if turn is not None:
            self._accept_turn(turn)

    def _reset_plan_boundary(self) -> None:
        if _is_plan_boundary(self._current):
            self._current = None

    def _accept_turn(self, turn: _AssistantTurn) -> None:
        current = self._current
        if current is None:
            self._start_new_bubble(turn)
            return
        self._merge_current_bubble(current, turn)

    def _start_new_bubble(self, turn: _AssistantTurn) -> None:
        current = _start_bubble(turn, len(self._entries))
        self._entries.append(current.bubble)
        self._current = current

    def _merge_current_bubble(self, current: _BubbleState, turn: _AssistantTurn) -> None:
        merged = _merge_bubble(current, turn)
        self._entries[merged.entry_index] = merged.bubble
        self._current = merged


def dump_confirmation(confirmation: IntentConfirmation) -> dict:
    """意图确认留档的传输结构。"""
    return confirmation.model_dump(mode="json", exclude={"session_id"}, exclude_none=True)


def dump_prompt(prompt: OptionPrompt) -> dict:
    """选项征询单的传输结构。"""
    return {
        "prompt_id": prompt.prompt_id,
        "message_id": prompt.message_id,
        "questions": [question.model_dump() for question in prompt.questions],
        "status": prompt.status,
        "answers": [answer.model_dump(exclude_none=True) for answer in prompt.answers],
        "created_at": prompt.created_at,
    }


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
    suspended_anchors = _anchor_ids(confirmations) | _anchor_ids(prompts)

    # 先按对话顺序合并消息，再把任务卡和成品卡插回对应位置。
    entries = _build_bubbles(messages, suspended_anchors, plan_anchors)
    for card in _plan_cards(graph, products):
        _insert_anchored_card(entries, card)

    # 已回答的确认和选项折叠进原助手气泡，供前端回看。
    _fold_confirmation_recaps(entries, confirmations)
    _fold_option_recaps(entries, prompts)

    # 开放门禁单独返回，阶段文案由当前门禁和任务状态共同派生。
    open_confirmation = next((item for item in confirmations if item.status == "open"), None)
    open_prompt = next((item for item in prompts if item.status == "open"), None)

    return {
        "bubbles": [entry.model_dump(mode="json") for entry in entries],
        "graph": graph_dump,
        "intent_state": intent_state.model_dump(mode="json"),
        "open_confirmation": dump_confirmation(open_confirmation) if open_confirmation else None,
        "open_option_prompt": dump_prompt(open_prompt) if open_prompt else None,
        "stage": _derive_stage(graph.nodes, open_confirmation, open_prompt),
        "needs_resume": needs_resume,
    }


def _build_bubbles(
    messages: list[MessageView],
    suspended_anchors: set[str],
    plan_anchors: set[str],
) -> list[BubbleEntry]:
    """按对话顺序产出渲染条目：一次交互链路的助手轮次合并成单气泡。"""
    accumulator = _BubbleAccumulator(suspended_anchors, plan_anchors)
    for message in messages:
        accumulator.consume(message)
    return accumulator.entries


def _classify_assistant_turn(
    message: MessageView,
    suspended_anchors: set[str],
    plan_anchors: set[str],
) -> Optional[_AssistantTurn]:
    """把有效助手消息转换为合并阶段需要的状态。"""
    has_content = bool(message.content and message.content.strip())
    has_tools = bool(message.tools)
    if not has_content and not has_tools:
        return None
    return _AssistantTurn(
        message=message,
        has_content=has_content,
        suspended=(message.id in suspended_anchors or (not has_content and has_tools)),
        plan_created=message.id in plan_anchors,
    )


def _start_bubble(turn: _AssistantTurn, entry_index: int) -> _BubbleState:
    """从首条有效助手消息创建气泡状态。"""
    message = turn.message
    bubble = AssistantBubble(
        id=message.id,
        content=message.content or "",
        tools=list(message.tools),
        message_ids=[message.id] if message.id else [],
        recaps=[],
        suspended=turn.suspended,
    )
    return _BubbleState(
        bubble=bubble,
        plan_created=turn.plan_created,
        entry_index=entry_index,
    )


def _merge_bubble(
    current: _BubbleState,
    turn: _AssistantTurn,
) -> _BubbleState:
    """把后续助手消息合并到当前气泡状态。"""
    message = turn.message
    separator = "\n\n" if current.bubble.content and turn.has_content else ""
    content = current.bubble.content + separator + (message.content if turn.has_content else "")
    message_ids = current.bubble.message_ids
    if message.id and message.id not in message_ids:
        message_ids = [*message_ids, message.id]
    return _BubbleState(
        bubble=current.bubble.model_copy(update={
            "content": content,
            "tools": [*current.bubble.tools, *message.tools],
            "message_ids": message_ids,
            "suspended": turn.suspended,
        }),
        plan_created=current.plan_created or turn.plan_created,
        entry_index=current.entry_index,
    )


def _is_plan_boundary(state: Optional[_BubbleState]) -> bool:
    """成功建图的待回执气泡是流水线边界。"""
    return state is not None and state.bubble.suspended and state.plan_created


def _anchor_ids(items: Iterable[Union[IntentConfirmation, OptionPrompt]]) -> set[str]:
    """留档记录锚定的助手消息标识集合，缺锚点的忽略。"""
    return {item.message_id for item in items if item.message_id is not None}


def _plan_cards(graph: TaskGraph, products: list[DeliveredProduct]) -> list[Union[TaskCard, ProductCard]]:
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


def _find_bubble(entries: list[BubbleEntry], message_id: str) -> Optional[tuple[int, AssistantBubble]]:
    for index, entry in enumerate(entries):
        if not isinstance(entry, AssistantBubble) or message_id not in entry.message_ids:
            continue
        return index, entry
    return None


def _insert_anchored_card(entries: list[BubbleEntry], card: Union[TaskCard, ProductCard]) -> None:
    """卡片插到锚点气泡之后，同锚卡片按投影顺序排列。"""
    anchor_message_id = card.anchor_message_id
    if anchor_message_id is None:
        return
    found = _find_bubble(entries, anchor_message_id)
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


def _fold_confirmation_recaps(entries: list[BubbleEntry], confirmations: list[IntentConfirmation]) -> None:
    for confirmation in confirmations:
        if confirmation.status != "answered" or confirmation.message_id is None:
            continue
        _append_recap(entries, confirmation.message_id, IntentRecap(
            id=f"intent-confirm:{confirmation.confirmation_id}",
            intent_state=dump_confirmation(confirmation),
        ))


def _fold_option_recaps(entries: list[BubbleEntry], prompts: list[OptionPrompt]) -> None:
    for prompt in prompts:
        if prompt.status != "answered" or prompt.message_id is None:
            continue
        _append_recap(entries, prompt.message_id, OptionRecap(
            id=f"option:{prompt.prompt_id}",
            option_prompt=dump_prompt(prompt),
        ))


def _append_recap(entries: list[BubbleEntry], anchor: str, recap: Recap) -> None:
    found = _find_bubble(entries, anchor)
    if found is None:
        return
    index, bubble = found
    entries[index] = bubble.model_copy(update={"recaps": [*bubble.recaps, recap]})


def _derive_stage(
    tasks: list[TaskNodeView],
    open_confirmation: Optional[IntentConfirmation],
    open_prompt: Optional[OptionPrompt],
) -> str:
    """从任务图快照与开放门禁派生会话阶段文案，门禁优先。"""
    return (
        _open_gate_stage(open_confirmation, open_prompt)
        or _active_task_stage(tasks)
        or ("已完成" if _has_finished_product(tasks) else None)
        or "自由对话"
    )


def _open_gate_stage(open_confirmation: Optional[IntentConfirmation],
    open_prompt: Optional[OptionPrompt],
) -> Optional[str]:
    if open_prompt is not None:
        return "等待选择"
    if open_confirmation is not None:
        return "等待确认"
    return None


def _active_task_stage(tasks: list[TaskNodeView]) -> Optional[str]:
    active = [task for task in tasks if task.is_stage_active()]
    if not active:
        return None
    task = min(active, key=lambda task_node: task_node.stage_sort_key())
    profile = AGENT_PROFILES[task.agent_type]
    return f"{profile.display_name} · {_TASK_STATE_LABELS[task.status]}"


def _has_finished_product(tasks: list[TaskNodeView]) -> bool:
    return any(
        task.status == TaskStatus.FINISHED and task.agent_type == AgentType.FINALIZE
        for task in tasks
    )
