"""
Message mention model for the Collaboration module.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MessageMention(Base):
    """Tracks @mentions in messages for notification routing."""

    __tablename__ = "message_mention"
    __table_args__ = ({"schema": "collab"},)

    mention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collab.message.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentioned_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    # Relationships
    message = relationship("Message", back_populates="mentions")
    person = relationship(
        "Person",
        primaryjoin="MessageMention.mentioned_person_id == Person.id",
        foreign_keys="MessageMention.mentioned_person_id",
        lazy="joined",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Mention {self.mentioned_person_id} in {self.message_id}>"
