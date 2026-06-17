"""
Message reaction model for the Collaboration module.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MessageReaction(Base):
    """Emoji reaction on a message."""

    __tablename__ = "message_reaction"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "person_id", "emoji",
            name="uq_collab_reaction",
        ),
        {"schema": "collab"},
    )

    reaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.message.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
    )
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    # Relationships
    message = relationship("Message", back_populates="reactions")
    person = relationship(
        "Person",
        primaryjoin="MessageReaction.person_id == Person.id",
        foreign_keys="MessageReaction.person_id",
        lazy="joined",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Reaction {self.emoji} by {self.person_id}>"
