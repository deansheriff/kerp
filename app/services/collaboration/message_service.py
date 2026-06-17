"""
Message service — sending, editing, deleting, pinning, reactions, search.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.collaboration.conversation import Conversation
from app.models.collaboration.mention import MessageMention
from app.models.collaboration.message import Message, MessageType
from app.models.collaboration.participant import ConversationParticipant
from app.models.collaboration.reaction import MessageReaction

logger = logging.getLogger(__name__)


class MessageService:
    """Manage messages within conversations."""

    @staticmethod
    def send_message(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str | None = None,
        parent_message_id: uuid.UUID | None = None,
        quoted_message_id: uuid.UUID | None = None,
        mentioned_person_ids: list[uuid.UUID] | None = None,
    ) -> Message:
        """Send a message. Verifies membership, creates mentions, updates unread counts."""
        # Verify sender is active participant
        participant = db.scalar(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == sender_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if not participant:
            raise PermissionError("Not a member of this conversation.")

        msg_type = MessageType.TEXT
        if not content:
            msg_type = MessageType.FILE_ONLY

        msg = Message(
            conversation_id=conversation_id,
            organization_id=org_id,
            sender_id=sender_id,
            content=content,
            message_type=msg_type,
            parent_message_id=parent_message_id,
            quoted_message_id=quoted_message_id,
        )
        db.add(msg)
        db.flush()

        # Create mentions
        if mentioned_person_ids:
            for pid in mentioned_person_ids:
                db.add(MessageMention(
                    message_id=msg.message_id,
                    mentioned_person_id=pid,
                ))

        # Increment unread_count for all other active participants
        db.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id != sender_id,
                ConversationParticipant.left_at.is_(None),
            )
            .values(unread_count=ConversationParticipant.unread_count + 1)
        )

        # Update conversation updated_at
        db.execute(
            update(Conversation)
            .where(Conversation.conversation_id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )

        db.flush()
        db.refresh(msg)
        return msg

    @staticmethod
    def list_messages(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        before_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> dict:
        """Cursor-paginated message listing. Verifies membership."""
        # Verify membership
        participant = db.scalar(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if not participant:
            return {"messages": [], "has_more": False}

        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.organization_id == org_id,
            )
            .order_by(Message.created_at.desc())
            .limit(limit + 1)
        )

        if before_id:
            before_msg = db.get(Message, before_id)
            if before_msg:
                stmt = stmt.where(Message.created_at < before_msg.created_at)

        messages_raw = list(db.scalars(stmt).unique().all())
        has_more = len(messages_raw) > limit
        messages_raw = messages_raw[:limit]

        messages = []
        for msg in reversed(messages_raw):  # Oldest first for display
            sender = msg.sender
            msg_data = {
                "message_id": str(msg.message_id),
                "conversation_id": str(msg.conversation_id),
                "sender_id": str(msg.sender_id),
                "sender_name": _person_name(sender),
                "sender_initials": _person_initials(sender),
                "content": msg.content if not msg.is_deleted else None,
                "message_type": msg.message_type.value,
                "is_deleted": msg.is_deleted,
                "is_edited": msg.is_edited,
                "is_pinned": msg.is_pinned,
                "parent_message_id": str(msg.parent_message_id) if msg.parent_message_id else None,
                "quoted_message_id": str(msg.quoted_message_id) if msg.quoted_message_id else None,
                "quoted_content": None,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
                "is_own": msg.sender_id == person_id,
                "attachments": [],
                "mentions": [],
                "reactions": {},
            }

            # Quoted message preview
            if msg.quoted_message and not msg.quoted_message.is_deleted:
                msg_data["quoted_content"] = {
                    "content": (msg.quoted_message.content or "")[:200],
                    "sender_name": _person_name(msg.quoted_message.sender),
                }

            # Attachments
            for att in (msg.attachments or []):
                msg_data["attachments"].append({
                    "attachment_id": str(att.attachment_id),
                    "file_name": att.file_name,
                    "content_type": att.content_type,
                    "file_size": att.file_size,
                    "is_image": att.content_type.startswith("image/") if att.content_type else False,
                    "download_url": f"/collaboration/api/attachments/{att.attachment_id}/download",
                })

            # Mentions
            for mention in (msg.mentions or []):
                msg_data["mentions"].append({
                    "person_id": str(mention.mentioned_person_id),
                    "name": _person_name(mention.person),
                })

            # Reactions (grouped by emoji)
            reaction_groups: dict[str, list[str]] = {}
            for react in (msg.reactions or []):
                if react.emoji not in reaction_groups:
                    reaction_groups[react.emoji] = []
                reaction_groups[react.emoji].append(str(react.person_id))
            msg_data["reactions"] = reaction_groups

            messages.append(msg_data)

        return {"messages": messages, "has_more": has_more}

    @staticmethod
    def edit_message(
        db: Session,
        org_id: uuid.UUID,
        message_id: uuid.UUID,
        person_id: uuid.UUID,
        new_content: str,
    ) -> bool:
        """Edit own message. Returns True on success."""
        msg = db.scalar(
            select(Message).where(
                Message.message_id == message_id,
                Message.organization_id == org_id,
                Message.sender_id == person_id,
                Message.is_deleted.is_(False),
            )
        )
        if not msg:
            return False

        msg.content = new_content
        msg.is_edited = True
        msg.edited_at = datetime.utcnow()
        db.flush()
        return True

    @staticmethod
    def delete_message(
        db: Session,
        org_id: uuid.UUID,
        message_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> bool:
        """Soft-delete own message."""
        msg = db.scalar(
            select(Message).where(
                Message.message_id == message_id,
                Message.organization_id == org_id,
                Message.sender_id == person_id,
                Message.is_deleted.is_(False),
            )
        )
        if not msg:
            return False

        msg.is_deleted = True
        msg.deleted_at = datetime.utcnow()
        msg.deleted_by_id = person_id
        db.flush()
        return True

    @staticmethod
    def pin_message(
        db: Session,
        org_id: uuid.UUID,
        message_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> bool:
        """Toggle pin on a message. Returns new pin state."""
        msg = db.scalar(
            select(Message).where(
                Message.message_id == message_id,
                Message.organization_id == org_id,
                Message.is_deleted.is_(False),
            )
        )
        if not msg:
            return False

        if msg.is_pinned:
            msg.is_pinned = False
            msg.pinned_by_id = None
            msg.pinned_at = None
        else:
            msg.is_pinned = True
            msg.pinned_by_id = person_id
            msg.pinned_at = datetime.utcnow()
        db.flush()
        return msg.is_pinned

    @staticmethod
    def toggle_reaction(
        db: Session,
        org_id: uuid.UUID,
        message_id: uuid.UUID,
        person_id: uuid.UUID,
        emoji: str,
    ) -> bool:
        """Toggle reaction. Returns True if added, False if removed."""
        existing = db.scalar(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.person_id == person_id,
                MessageReaction.emoji == emoji,
            )
        )
        if existing:
            db.delete(existing)
            db.flush()
            return False
        else:
            db.add(MessageReaction(
                message_id=message_id,
                person_id=person_id,
                emoji=emoji,
            ))
            db.flush()
            return True

    @staticmethod
    def mark_read(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        last_message_id: uuid.UUID,
    ) -> None:
        """Mark conversation as read up to a specific message."""
        db.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.person_id == person_id,
            )
            .values(
                last_read_message_id=last_message_id,
                last_read_at=datetime.utcnow(),
                unread_count=0,
            )
        )
        db.flush()

    @staticmethod
    def search_messages(
        db: Session,
        org_id: uuid.UUID,
        person_id: uuid.UUID,
        query: str,
        conversation_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search messages across conversations the user belongs to."""
        # Get conversation IDs this person is a member of
        member_conv_ids = (
            select(ConversationParticipant.conversation_id)
            .where(
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
        )

        term = f"%{query}%"
        stmt = (
            select(Message)
            .where(
                Message.organization_id == org_id,
                Message.conversation_id.in_(member_conv_ids),
                Message.is_deleted.is_(False),
                Message.content.ilike(term),
            )
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        if conversation_id:
            stmt = stmt.where(Message.conversation_id == conversation_id)

        messages = list(db.scalars(stmt).unique().all())

        results = []
        for msg in messages:
            # Get conversation name
            conv = db.get(Conversation, msg.conversation_id)
            results.append({
                "message_id": str(msg.message_id),
                "conversation_id": str(msg.conversation_id),
                "conversation_name": conv.name if conv else "Direct Message",
                "conversation_type": conv.conversation_type.value if conv else "DIRECT",
                "sender_name": _person_name(msg.sender),
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return {"results": results, "query": query}


def _person_name(person) -> str:
    """Get display name from Person object."""
    if not person:
        return "Unknown"
    parts = []
    if getattr(person, "first_name", None):
        parts.append(person.first_name)
    if getattr(person, "last_name", None):
        parts.append(person.last_name)
    return " ".join(parts) if parts else (getattr(person, "email", None) or "Unknown")


def _person_initials(person) -> str:
    """Get initials from Person object."""
    if not person:
        return "?"
    first = (getattr(person, "first_name", None) or "")[:1].upper()
    last = (getattr(person, "last_name", None) or "")[:1].upper()
    return f"{first}{last}" if first else "?"
