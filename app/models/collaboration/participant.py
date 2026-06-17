"""
Conversation participant (membership) model.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ParticipantRole(str, enum.Enum):
    """Role within a conversation."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class ConversationParticipant(Base):
    """Membership of a person in a conversation."""

    __tablename__ = "conversation_participant"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "person_id",
            name="uq_collab_participant",
        ),
        {"schema": "collab"},
    )

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[ParticipantRole] = mapped_column(
        Enum(ParticipantRole), nullable=False, default=ParticipantRole.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_muted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    unread_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    # Relationships
    conversation = relationship(
        "Conversation", back_populates="participants",
    )
    person = relationship(
        "Person",
        primaryjoin="ConversationParticipant.person_id == Person.id",
        foreign_keys="ConversationParticipant.person_id",
        lazy="joined",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Participant {self.person_id} in {self.conversation_id}>"
