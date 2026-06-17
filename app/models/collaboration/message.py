"""
Message model for the Collaboration module.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MessageType(str, enum.Enum):
    """Type of message."""

    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    FILE_ONLY = "FILE_ONLY"


class Message(Base):
    """A single chat message."""

    __tablename__ = "message"
    __table_args__ = (
        Index("ix_collab_msg_conv_created", "conversation_id", "created_at"),
        Index("ix_collab_msg_conv_pinned", "conversation_id", "is_pinned"),
        {"schema": "collab"},
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), nullable=False, default=MessageType.TEXT,
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.message.message_id"),
        nullable=True,
    )
    quoted_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.message.message_id"),
        nullable=True,
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    pinned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id"), nullable=True,
    )
    pinned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_edited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
        index=True,
    )

    # Relationships
    sender = relationship(
        "Person",
        primaryjoin="Message.sender_id == Person.id",
        foreign_keys="Message.sender_id",
        lazy="joined",
        viewonly=True,
    )
    attachments = relationship(
        "MessageAttachment",
        back_populates="message",
        lazy="selectin",
    )
    mentions = relationship(
        "MessageMention",
        back_populates="message",
        lazy="selectin",
    )
    reactions = relationship(
        "MessageReaction",
        back_populates="message",
        lazy="selectin",
    )
    quoted_message = relationship(
        "Message",
        remote_side="Message.message_id",
        primaryjoin="Message.quoted_message_id == Message.message_id",
        foreign_keys="Message.quoted_message_id",
        lazy="joined",
        viewonly=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Message {self.message_id}>"
