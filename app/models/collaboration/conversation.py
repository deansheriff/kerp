"""
Conversation model for the Collaboration module.
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
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ConversationType(str, enum.Enum):
    """Type of conversation."""

    DIRECT = "DIRECT"
    GROUP = "GROUP"
    CHANNEL = "CHANNEL"


class Conversation(Base):
    """A chat conversation (DM, group, or project channel)."""

    __tablename__ = "conversation"
    __table_args__ = (
        Index("ix_collab_conv_org_type", "organization_id", "conversation_type"),
        Index("ix_collab_conv_linked", "linked_entity_type", "linked_entity_id"),
        {"schema": "collab"},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    conversation_type: Mapped[ConversationType] = mapped_column(
        Enum(ConversationType), nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id"), nullable=True,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    linked_entity_type: Mapped[str | None] = mapped_column(
        String(80), nullable=True,
    )
    linked_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    participants = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        lazy="selectin",
    )
    creator = relationship(
        "Person",
        primaryjoin="Conversation.created_by_id == Person.id",
        foreign_keys="Conversation.created_by_id",
        lazy="joined",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.conversation_id} {self.conversation_type.value}>"
