"""Employee collaboration and chat models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.finance.core_org.project import Project
    from app.models.person import Person


class ConversationType(str, enum.Enum):
    """Conversation grouping."""

    DIRECT = "DIRECT"
    GROUP = "GROUP"
    PROJECT = "PROJECT"


class ParticipantRole(str, enum.Enum):
    """Participant role inside a conversation."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Conversation(Base):
    """A direct, group, or project-linked employee conversation."""

    __tablename__ = "conversation"
    __table_args__ = (
        Index("ix_collab_conversation_org_updated", "organization_id", "updated_at"),
        Index("ix_collab_conversation_project", "organization_id", "project_id"),
        {"schema": "collab"},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    conversation_type: Mapped[ConversationType] = mapped_column(
        Enum(
            ConversationType,
            name="collab_conversation_type",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=ConversationType.GROUP,
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.project.project_id"),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    created_by: Mapped[Person] = relationship(
        "Person",
        primaryjoin="Conversation.created_by_id == Person.id",
        foreign_keys="Conversation.created_by_id",
        lazy="joined",
        viewonly=True,
    )
    project: Mapped[Project | None] = relationship(
        "Project",
        lazy="selectin",
        viewonly=True,
    )
    participants: Mapped[list[ConversationParticipant]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list[ConversationMessage]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
    )


class ConversationParticipant(Base):
    """Membership and read state for a person in a conversation."""

    __tablename__ = "conversation_participant"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "person_id",
            name="uq_collab_participant_conversation_person",
        ),
        Index("ix_collab_participant_person", "organization_id", "person_id"),
        {"schema": "collab"},
    )

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
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
        Enum(
            ParticipantRole,
            name="collab_participant_role",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=ParticipantRole.MEMBER,
    )
    is_muted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation",
        back_populates="participants",
    )
    person: Mapped[Person] = relationship(
        "Person",
        primaryjoin="ConversationParticipant.person_id == Person.id",
        foreign_keys="ConversationParticipant.person_id",
        lazy="joined",
        viewonly=True,
    )


class ConversationMessage(Base):
    """A message posted to a conversation."""

    __tablename__ = "conversation_message"
    __table_args__ = (
        Index("ix_collab_message_conversation_created", "conversation_id", "created_at"),
        Index("ix_collab_message_sender", "organization_id", "sender_id"),
        {"schema": "collab"},
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
        index=True,
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.conversation_message.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped[Person] = relationship(
        "Person",
        primaryjoin="ConversationMessage.sender_id == Person.id",
        foreign_keys="ConversationMessage.sender_id",
        lazy="joined",
        viewonly=True,
    )
    attachments: Mapped[list[ConversationAttachment]] = relationship(
        "ConversationAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class ConversationAttachment(Base):
    """File attached to a collaboration message."""

    __tablename__ = "conversation_attachment"
    __table_args__ = (
        Index("ix_collab_attachment_message", "message_id"),
        {"schema": "collab"},
    )

    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.conversation_message.message_id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    message: Mapped[ConversationMessage] = relationship(
        "ConversationMessage",
        back_populates="attachments",
    )
    uploaded_by: Mapped[Person] = relationship(
        "Person",
        primaryjoin="ConversationAttachment.uploaded_by_id == Person.id",
        foreign_keys="ConversationAttachment.uploaded_by_id",
        lazy="joined",
        viewonly=True,
    )

    @property
    def is_image(self) -> bool:
        """Whether the attachment can be previewed as an image."""
        return self.content_type.startswith("image/")
