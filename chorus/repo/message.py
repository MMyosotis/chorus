"""消息表的唯一 SQL 入口，按消息粒度逐行存储。

助手消息的展示元数据存轨迹表，靠消息标识关联聚合。形状转换集中在转换函数，
供只存原始事实的本表与压缩现场的现场表共用。
"""
from __future__ import annotations

from typing import Optional, cast

from sqlalchemy import select, update

from chorus.domain.message import (
    AssistantMessage,
    Message,
    ToolCallSpec,
    ToolMessage,
    UserMessage,
)
from chorus.repo.base import BaseRepository, read, write
from chorus.repo.models import MessageRecord


def _parse_tool_calls(raw) -> list[ToolCallSpec]:
    """解析工具调用列表，脏数据退化为空。"""
    if not raw:
        return []
    try:
        return [ToolCallSpec(**tc) for tc in raw]
    except (TypeError, ValueError):
        return []


def _dump_tool_calls(tool_calls: Optional[list[ToolCallSpec]]):
    if not tool_calls:
        return None
    return [call.model_dump() for call in tool_calls]


def to_domain(r) -> Message:
    if r.role == "user":
        return UserMessage(
            id=r.id, session_id=r.session_id, created_at=r.created_at,
            content=r.content or "",
        )
    if r.role == "assistant":
        return AssistantMessage(
            id=r.id, session_id=r.session_id, created_at=r.created_at,
            content=r.content, tool_calls=_parse_tool_calls(r.tool_calls_json),
        )
    if r.role == "tool":
        return ToolMessage(
            id=r.id, session_id=r.session_id, created_at=r.created_at,
            tool_call_id=r.tool_call_id or "", name=r.tool_name or "",
            content=r.content or "",
        )
    raise ValueError(f"unknown role: {r.role}")


def from_domain(msg: Message, record_cls=MessageRecord):
    if msg.role == "user":
        return record_cls(
            id=msg.id, session_id=msg.session_id, role="user",
            content=msg.content, created_at=msg.created_at,
        )
    if msg.role == "assistant":
        return record_cls(
            id=msg.id, session_id=msg.session_id, role="assistant",
            content=msg.content, tool_calls_json=_dump_tool_calls(msg.tool_calls),
            created_at=msg.created_at,
        )
    if msg.role == "tool":
        return record_cls(
            id=msg.id, session_id=msg.session_id, role="tool",
            tool_call_id=msg.tool_call_id, tool_name=msg.name,
            content=msg.content, created_at=msg.created_at,
        )
    raise TypeError(f"unsupported message role: {msg.role}")


class MessageRepository(BaseRepository):
    @write
    def append(self, db, message: Message) -> None:
        """单条消息入库。"""
        db.add(from_domain(message))

    @read
    def list_by_session(self, db, session_id: str) -> list[Message]:
        """按标识升序返回该会话全部消息，即写入顺序。"""
        rs = db.scalars(
            select(MessageRecord).where(MessageRecord.session_id == session_id)
            .order_by(MessageRecord.id)
        ).all()
        return [to_domain(r) for r in rs]

    @read
    def get(self, db, message_id: str) -> Optional[Message]:
        r = db.get(MessageRecord, message_id)
        return to_domain(r) if r else None

    @read
    def find_last_tool_by_name(self, db, session_id: str, name: str) -> Optional[ToolMessage]:
        r = db.scalars(
            select(MessageRecord)
            .where(
                MessageRecord.session_id == session_id,
                MessageRecord.role == "tool",
                MessageRecord.tool_name == name,
            )
            .order_by(MessageRecord.id.desc())
            .limit(1)
        ).first()
        return cast(Optional[ToolMessage], to_domain(r)) if r else None

    @write
    def update_content(self, db, message_id: str, content: str) -> None:
        db.execute(
            update(MessageRecord).where(MessageRecord.id == message_id).values(content=content)
        )
