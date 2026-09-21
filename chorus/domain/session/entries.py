"""会话视图中的对话条目和卡片模型。"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chorus.domain.intent import IntentConfirmationView
from chorus.domain.option import OptionPromptView
from chorus.domain.task.graph import TaskNodeResponse
from chorus.domain.task.products import DeliveredProduct
from chorus.domain.trace import ToolInvocation


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
    intent_state: IntentConfirmationView


class OptionRecap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    option_prompt: OptionPromptView


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
