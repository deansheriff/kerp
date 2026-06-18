"""
Conversation service — CRUD for conversations and participants.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.collaboration.conversation import Conversation, ConversationType
from app.models.collaboration.message import Message
from app.models.collaboration.participant import (
    ConversationParticipant,
    ParticipantRole,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """Manage conversations, participants, and membership."""

    @staticmethod
    def create_direct(
        db: Session,
        org_id: uuid.UUID,
        person_a_id: uuid.UUID,
        person_b_id: uuid.UUID,
    ) -> Conversation:
        """Find existing DM or create a new one between two people."""
        # Look for an existing DIRECT conversation with both participants
        subq_a = (
            select(ConversationParticipant.conversation_id)
            .where(
                ConversationParticipant.person_id == person_a_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        subq_b = (
            select(ConversationParticipant.conversation_id)
            .where(
                ConversationParticipant.person_id == person_b_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        existing = db.scalar(
            select(Conversation).where(
                Conversation.organization_id == org_id,
                Conversation.conversation_type == ConversationType.DIRECT,
                Conversation.is_archived.is_(False),
                Conversation.conversation_id.in_(subq_a),
                Conversation.conversation_id.in_(subq_b),
            )
        )
        if existing:
            return existing

        now = datetime.utcnow()
        conv = Conversation(
            organization_id=org_id,
            conversation_type=ConversationType.DIRECT,
            created_by_id=person_a_id,
            created_at=now,
            updated_at=now,
        )
        db.add(conv)
        db.flush()

        for pid in (person_a_id, person_b_id):
            db.add(ConversationParticipant(
                conversation_id=conv.conversation_id,
                person_id=pid,
                role=ParticipantRole.MEMBER,
            ))
        db.flush()
        return conv

    @staticmethod
    def create_group(
        db: Session,
        org_id: uuid.UUID,
        name: str,
        description: str | None,
        creator_id: uuid.UUID,
        member_ids: list[uuid.UUID],
    ) -> Conversation:
        """Create a GROUP conversation."""
        now = datetime.utcnow()
        conv = Conversation(
            organization_id=org_id,
            conversation_type=ConversationType.GROUP,
            name=name,
            description=description,
            created_by_id=creator_id,
            created_at=now,
            updated_at=now,
        )
        db.add(conv)
        db.flush()

        # Creator is OWNER
        db.add(ConversationParticipant(
            conversation_id=conv.conversation_id,
            person_id=creator_id,
            role=ParticipantRole.OWNER,
        ))

        # Members
        for pid in member_ids:
            if pid != creator_id:
                db.add(ConversationParticipant(
                    conversation_id=conv.conversation_id,
                    person_id=pid,
                    role=ParticipantRole.MEMBER,
                ))
        db.flush()
        return conv

    @staticmethod
    def create_channel(
        db: Session,
        org_id: uuid.UUID,
        name: str,
        creator_id: uuid.UUID,
        linked_entity_type: str,
        linked_entity_id: uuid.UUID,
        member_ids: list[uuid.UUID] | None = None,
    ) -> Conversation:
        """Create a CHANNEL linked to an ERP record."""
        now = datetime.utcnow()
        conv = Conversation(
            organization_id=org_id,
            conversation_type=ConversationType.CHANNEL,
            name=name,
            created_by_id=creator_id,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
            created_at=now,
            updated_at=now,
        )
        db.add(conv)
        db.flush()

        db.add(ConversationParticipant(
            conversation_id=conv.conversation_id,
            person_id=creator_id,
            role=ParticipantRole.OWNER,
        ))
        for pid in (member_ids or []):
            if pid != creator_id:
                db.add(ConversationParticipant(
                    conversation_id=conv.conversation_id,
                    person_id=pid,
                    role=ParticipantRole.MEMBER,
                ))
        db.flush()
        return conv

    @staticmethod
    def list_conversations(
        db: Session,
        org_id: uuid.UUID,
        person_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        per_page: int = 30,
    ) -> dict:
        """List conversations for a person with last message and unread counts."""
        # Subquery for latest message per conversation
        latest_msg = (
            select(
                Message.conversation_id,
                func.max(Message.created_at).label("last_msg_at"),
            )
            .where(Message.is_deleted.is_(False))
            .group_by(Message.conversation_id)
            .subquery()
        )

        stmt = (
            select(
                Conversation,
                ConversationParticipant.unread_count,
                ConversationParticipant.is_muted,
                latest_msg.c.last_msg_at,
            )
            .join(
                ConversationParticipant,
                and_(
                    ConversationParticipant.conversation_id == Conversation.conversation_id,
                    ConversationParticipant.person_id == person_id,
                    ConversationParticipant.left_at.is_(None),
                ),
            )
            .outerjoin(
                latest_msg,
                latest_msg.c.conversation_id == Conversation.conversation_id,
            )
            .where(
                Conversation.organization_id == org_id,
                Conversation.is_archived.is_(False),
            )
            .order_by(latest_msg.c.last_msg_at.desc().nullslast())
        )

        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Conversation.name.ilike(term),
                    Conversation.description.ilike(term),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        offset = (page - 1) * per_page
        rows = db.execute(stmt.offset(offset).limit(per_page)).all()

        conversations = []
        for conv, unread, muted, last_msg_at in rows:
            # Get the last message text
            last_msg = None
            if last_msg_at:
                last_msg_obj = db.scalar(
                    select(Message)
                    .where(
                        Message.conversation_id == conv.conversation_id,
                        Message.is_deleted.is_(False),
                    )
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                if last_msg_obj:
                    last_msg = {
                        "content": (last_msg_obj.content or "")[:100],
                        "sender_name": _person_display_name(last_msg_obj.sender),
                        "created_at": last_msg_obj.created_at.isoformat() if last_msg_obj.created_at else None,
                    }

            # For DMs, derive name from the other participant
            display_name = conv.name
            other_person = None
            if conv.conversation_type == ConversationType.DIRECT:
                for p in (conv.participants or []):
                    if p.person_id != person_id and p.left_at is None:
                        other_person = p.person
                        display_name = _person_display_name(p.person)
                        break

            conversations.append({
                "conversation_id": str(conv.conversation_id),
                "type": conv.conversation_type.value,
                "name": display_name or "Conversation",
                "description": conv.description,
                "unread_count": unread or 0,
                "is_muted": muted,
                "last_message": last_msg,
                "linked_entity_type": conv.linked_entity_type,
                "linked_entity_id": str(conv.linked_entity_id) if conv.linked_entity_id else None,
                "participant_count": len([p for p in (conv.participants or []) if p.left_at is None]),
            })

        return {
            "conversations": conversations,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }

    @staticmethod
    def get_conversation(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> Conversation | None:
        """Get a conversation with membership check."""
        conv = db.scalar(
            select(Conversation).where(
                Conversation.conversation_id == conversation_id,
                Conversation.organization_id == org_id,
            )
        )
        if not conv:
            return None

        # Verify membership
        participant = db.scalar(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if not participant:
            return None

        return conv

    @staticmethod
    def get_participant_person_ids(
        db: Session,
        conversation_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Get active participant person IDs for a conversation."""
        rows = db.scalars(
            select(ConversationParticipant.person_id).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.left_at.is_(None),
            )
        ).all()
        return list(rows)

    @staticmethod
    def add_participants(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_ids: list[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> None:
        """Add members to a GROUP/CHANNEL conversation."""
        conv = db.scalar(
            select(Conversation).where(
                Conversation.conversation_id == conversation_id,
                Conversation.organization_id == org_id,
            )
        )
        if not conv or conv.conversation_type == ConversationType.DIRECT:
            return

        existing = set(db.scalars(
            select(ConversationParticipant.person_id).where(
                ConversationParticipant.conversation_id == conversation_id,
            )
        ).all())

        for pid in person_ids:
            if pid in existing:
                # Re-activate if they left
                db.execute(
                    update(ConversationParticipant)
                    .where(
                        ConversationParticipant.conversation_id == conversation_id,
                        ConversationParticipant.person_id == pid,
                    )
                    .values(left_at=None, role=ParticipantRole.MEMBER)
                )
            else:
                db.add(ConversationParticipant(
                    conversation_id=conversation_id,
                    person_id=pid,
                    role=ParticipantRole.MEMBER,
                ))
        db.flush()

    @staticmethod
    def remove_participant(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """Remove a member from a conversation (sets left_at)."""
        db.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
            .values(left_at=datetime.utcnow())
        )
        db.flush()

    @staticmethod
    def mute_conversation(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        muted: bool,
    ) -> None:
        """Toggle mute for a user in a conversation."""
        db.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == person_id,
            )
            .values(is_muted=muted)
        )
        db.flush()

    @staticmethod
    def archive_conversation(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> None:
        """Archive a conversation."""
        db.execute(
            update(Conversation)
            .where(
                Conversation.conversation_id == conversation_id,
                Conversation.organization_id == org_id,
            )
            .values(is_archived=True, updated_at=datetime.utcnow())
        )
        db.flush()

    @staticmethod
    def get_total_unread(
        db: Session,
        org_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> int:
        """Get total unread count across all conversations."""
        total = db.scalar(
            select(func.coalesce(func.sum(ConversationParticipant.unread_count), 0))
            .join(
                Conversation,
                Conversation.conversation_id == ConversationParticipant.conversation_id,
            )
            .where(
                Conversation.organization_id == org_id,
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        return int(total or 0)


def _person_display_name(person) -> str:
    """Get display name from a Person object."""
    if not person:
        return "Unknown"
    parts = []
    if getattr(person, "first_name", None):
        parts.append(person.first_name)
    if getattr(person, "last_name", None):
        parts.append(person.last_name)
    return " ".join(parts) if parts else (getattr(person, "email", None) or "Unknown")
