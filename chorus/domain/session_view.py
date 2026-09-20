"""会话视图装配：把消息、任务图、意图与选项留档折成前端直接渲染的成品结构。"""

from __future__ import annotations

from typing import Annotated, Iterable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.intent import IntentConfirmation, IntentState
from chorus.domain.message import MessageView
from chorus.domain.option import OptionPrompt
from chorus.domain.task.graph import TaskGraph, TaskNodeView, dump_task_graph
from chorus.domain.task.products import DeliveredProduct
from chorus.domain.task.profiles import AGENT_PROFILES
from chorus.domain.trace import ToolInvocation

_TASK_STATE_LABELS = {
    "running": "执行中",
    "awaiting_confirm": "等待确认",
    "failed": "需要处理",
}
_TASK_STATE_PRIORITY = {"failed": 0, "awaiting_confirm": 1, "running": 2}
_AGENT_PRIORITY = {
    agent_type: index
    for index, agent_type in enumerate(("idea", "script", "image", "finalize"))
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
    hil_suspended: bool = Field(exclude=True)
    pending_tools: bool = Field(exclude=True)
    plan_created: bool = Field(exclude=True)

    @property
    def suspended(self) -> bool:
        return self.hil_suspended or self.pending_tools


TaskCardKind = Literal["confirmed", "running", "hil", "recovery"]


class TaskCard(_ViewEntry):
    kind: TaskCardKind
    task: TaskNodeView
    anchor_message_id: Optional[str]


class ProductCard(_ViewEntry):
    kind: Literal["product"] = "product"
    product: DeliveredProduct
    anchor_message_id: Optional[str]


BubbleEntry = Annotated[
    Union[UserEntry, AssistantBubble, TaskCard, ProductCard],
    Field(discriminator="kind"),
]


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
    graph_dump = dump_task_graph(graph)
    plan_anchors = {node.message_id for node in graph.nodes if node.message_id}
    entries = _build_bubbles(
        messages,
        _anchor_ids(confirmations),
        _anchor_ids(prompts),
        plan_anchors,
    )
    for card in _plan_cards(graph, products):
        _insert_anchored_card(entries, card)
    _fold_recaps(entries, confirmations, prompts)
    open_confirmation = next((item for item in confirmations if item.status == "open"), None)
    open_prompt = next((item for item in prompts if item.status == "open"), None)
    return {
        "bubbles": [_dump_entry(entry) for entry in entries],
        "graph": graph_dump,
        "intent_state": intent_state.model_dump(mode="json"),
        "open_confirmation": dump_confirmation(open_confirmation) if open_confirmation else None,
        "open_option_prompt": dump_prompt(open_prompt) if open_prompt else None,
        "stage": _derive_stage(graph.nodes, open_confirmation, open_prompt),
        "needs_resume": needs_resume,
    }


def _build_bubbles(
    messages: list[MessageView],
    confirmation_anchors: set[str],
    prompt_anchors: set[str],
    plan_anchors: set[str],
) -> list[BubbleEntry]:
    """按对话顺序产出渲染条目：一次交互链路的助手轮次合并成单气泡。"""
    entries: list[BubbleEntry] = []
    current: Optional[AssistantBubble] = None
    for message in messages:
        if message.role != "assistant":
            entries.append(UserEntry(id=message.id, content=message.content))
            current = None
            continue
        if _is_plan_boundary(current):
            current = None
        starts_bubble = current is None
        current = _append_assistant_turn(
            current,
            message,
            message.id in confirmation_anchors or message.id in prompt_anchors,
            message.id in plan_anchors,
        )
        if current is None:
            continue
        if starts_bubble:
            entries.append(current)
        else:
            entries[-1] = current
    return entries


def _append_assistant_turn(
    current: Optional[AssistantBubble],
    message: MessageView,
    hil_suspended: bool,
    plan_created: bool,
) -> Optional[AssistantBubble]:
    has_content = bool(message.content and message.content.strip())
    has_tools = bool(message.tools)
    if not has_content and not has_tools:
        return current
    pending_tools = not has_content and has_tools
    if current is None:
        return AssistantBubble(
            id=message.id,
            content=message.content or "",
            tools=list(message.tools),
            message_ids=[message.id] if message.id else [],
            recaps=[],
            hil_suspended=hil_suspended,
            pending_tools=pending_tools,
            plan_created=plan_created,
        )
    separator = "\n\n" if current.content and has_content else ""
    content = current.content + separator + (message.content if has_content else "")
    message_ids = current.message_ids
    if message.id and message.id not in message_ids:
        message_ids = [*message_ids, message.id]
    return current.model_copy(update={
        "content": content,
        "tools": [*current.tools, *message.tools],
        "message_ids": message_ids,
        "hil_suspended": hil_suspended,
        "pending_tools": pending_tools,
        "plan_created": current.plan_created or plan_created,
    })


def _is_plan_boundary(bubble: Optional[AssistantBubble]) -> bool:
    """成功建图的待回执气泡是流水线边界。"""
    return bool(bubble and bubble.suspended and bubble.plan_created)


def _anchor_ids(items: Iterable[Union[IntentConfirmation, OptionPrompt]]) -> set[str]:
    """留档记录锚定的助手消息标识集合，缺锚点的忽略。"""
    return {item.message_id for item in items if item.message_id}


def _plan_cards(graph: TaskGraph, products: list[DeliveredProduct]) -> list[Union[TaskCard, ProductCard]]:
    """任务图快照与成品清单投影成对话区卡片，顺序即插入顺序。"""
    cards: list[Union[TaskCard, ProductCard]] = []
    for node in graph.nodes:
        if node.status == "finished" and node.agent_type != "finalize":
            cards.append(_task_card("confirmed", node))
    running = next((node for node in graph.nodes if node.status == "running"), None)
    if running is not None:
        cards.append(_task_card("running", running))
    for node in graph.nodes:
        if node.status == "awaiting_confirm":
            cards.append(_task_card("hil", node))
        elif node.status == "failed":
            cards.append(_task_card("recovery", node))
    cards.extend(
        ProductCard(
            id=f"product:{product.id}",
            product=product,
            anchor_message_id=product.message_id,
        )
        for product in products
        if product.message_id
    )
    return cards


def _task_card(kind: TaskCardKind, task: TaskNodeView) -> TaskCard:
    return TaskCard(
        kind=kind,
        id=f"{kind}:{task.id}",
        task=task,
        anchor_message_id=task.message_id,
    )


def _find_bubble(entries: list[BubbleEntry], message_id: str) -> Optional[tuple[int, AssistantBubble]]:
    for index, entry in enumerate(entries):
        if isinstance(entry, AssistantBubble) and message_id in entry.message_ids:
            return index, entry
    return None


def _insert_anchored_card(entries: list[BubbleEntry], card: Union[TaskCard, ProductCard]) -> None:
    """卡片插到锚点气泡之后，同锚卡片按投影顺序排列。"""
    if not card.anchor_message_id:
        return
    found = _find_bubble(entries, card.anchor_message_id)
    if found is None:
        return
    insert_index = found[0] + 1
    while insert_index < len(entries):
        candidate = entries[insert_index]
        if not isinstance(candidate, (TaskCard, ProductCard)):
            break
        if candidate.anchor_message_id != card.anchor_message_id:
            break
        insert_index += 1
    entries.insert(insert_index, card)


def _fold_recaps(
    entries: list[BubbleEntry],
    confirmations: list[IntentConfirmation],
    prompts: list[OptionPrompt],
) -> None:
    """已作答的意图确认与选项征询折进锚点气泡作回看条目。"""
    for confirmation in confirmations:
        if confirmation.status == "answered" and confirmation.message_id:
            _append_recap(entries, confirmation.message_id, IntentRecap(
                id=f"intent-confirm:{confirmation.confirmation_id}",
                intent_state=dump_confirmation(confirmation),
            ))
    for prompt in prompts:
        if prompt.status == "answered" and prompt.message_id:
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
    if open_prompt is not None:
        return "等待选择"
    if open_confirmation is not None:
        return "等待确认"
    active = [task for task in tasks if task.status in _TASK_STATE_PRIORITY]
    if active:
        task = min(active, key=_stage_priority)
        profile = AGENT_PROFILES.get(task.agent_type)
        role = profile.display_name if profile else task.agent_type
        return f"{role} · {_TASK_STATE_LABELS[task.status]}"
    if any(task.status == "finished" and task.agent_type == "finalize" for task in tasks):
        return "已完成"
    return "自由对话"


def _stage_priority(task: TaskNodeView) -> tuple[int, int, str, str]:
    return (
        _TASK_STATE_PRIORITY[task.status],
        _AGENT_PRIORITY.get(task.agent_type, len(_AGENT_PRIORITY)),
        task.agent_type,
        task.id,
    )


def _dump_entry(entry: BubbleEntry) -> dict:
    if isinstance(entry, AssistantBubble):
        data = entry.model_dump(mode="json")
        data["suspended"] = entry.suspended
        return data
    if isinstance(entry, TaskCard):
        data = entry.model_dump(mode="json", exclude={"task"})
        data["task"] = dump_task_graph(TaskGraph(
            pipeline_id=None,
            active=False,
            nodes=[entry.task],
        ))["tasks"][0]
        return data
    return entry.model_dump(mode="json")
