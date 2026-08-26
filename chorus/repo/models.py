"""所有表的 SQLAlchemy declarative Record，与现有 _DDL 列一一对应。

JSON 列用 JSON 类型，索引/外键/约束在类上声明；领域转换仍归各 repo。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("idx_session_updated", "updated_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    title_generated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("idx_messages_session_id", "session_id", "id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls_json: Mapped[Optional[list]] = mapped_column(JSON)
    tool_call_id: Mapped[Optional[str]] = mapped_column(Text)
    tool_name: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class ProviderMessageRecord(Base):
    __tablename__ = "provider_messages"
    __table_args__ = (Index("idx_provider_messages_session_id", "session_id", "id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls_json: Mapped[Optional[list]] = mapped_column(JSON)
    tool_call_id: Mapped[Optional[str]] = mapped_column(Text)
    tool_name: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class TraceRecord(Base):
    __tablename__ = "traces"
    __table_args__ = (
        Index("idx_traces_session_created_at", "session_id", "created_at"),
        Index("idx_traces_message", "message_id"),
        Index("idx_traces_task", "task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[str]] = mapped_column(Text)
    task_id: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="supervisor")
    phase: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class TaskRecord(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_session", "session_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[str]] = mapped_column(String)
    pipeline_id: Mapped[str] = mapped_column(String, nullable=False)
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)
    owner_id: Mapped[Optional[float]] = mapped_column(Float)


class TaskContentRecord(Base):
    __tablename__ = "task_content"

    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    invoke_message: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    feedback: Mapped[Optional[str]] = mapped_column(Text)


class TaskArtifactsRecord(Base):
    __tablename__ = "task_artifacts"

    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    artifacts: Mapped[dict] = mapped_column(JSON, nullable=False)


class TaskProgressRecord(Base):
    __tablename__ = "task_progress"

    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    composing_chars: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    composing_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    composing_label: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    last_signal: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    aside: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    activity_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    activity_detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class SettingsRecord(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class IntentStateRecord(Base):
    __tablename__ = "intent_states"
    __table_args__ = (CheckConstraint("progress_percent BETWEEN 0 AND 100"),)

    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    intent_status: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(Text, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class OptionPromptRecord(Base):
    __tablename__ = "option_prompts"
    __table_args__ = (Index("idx_option_prompts_session", "session_id"),)

    prompt_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[str]] = mapped_column(String)
    prompt: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class IntentConfirmationRecord(Base):
    __tablename__ = "intent_confirmations"
    __table_args__ = (Index("idx_intent_confirmations_session", "session_id"),)

    confirmation_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[str]] = mapped_column(String)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class CreatorMemoryRecord(Base):
    __tablename__ = "creator_memories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, server_default="reference")
    description: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visible_to: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
