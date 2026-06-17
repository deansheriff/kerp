"""Service layer for employee collaboration and chat."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.collaboration import (
    Conversation,
    ConversationAttachment,
    ConversationMessage,
    ConversationParticipant,
    ConversationType,
    ParticipantRole,
)
from app.models.notification import EntityType, NotificationType
from app.models.person import Person, PersonStatus
from app.services.common import coerce_uuid
from app.services.file_upload import (
    FileUploadError,
    format_file_size,
    get_collaboration_attachment_upload,
)
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationListItem:
    """Formatted conversation summary for the inbox."""

    conversation_id: str
    title: str
    subtitle: str
    conversation_type: str
    unread_count: int
    participant_count: int
    last_message: str
    last_message_at: datetime | None
    is_muted: bool


@dataclass(frozen=True)
class MessageAttachmentView:
    """Formatted message attachment."""

    attachment_id: str
    filename: str
    content_type: str
    file_size: str
    is_image: bool
    download_url: str


@dataclass(frozen=True)
class MessageView:
    """Formatted chat message."""

    message_id: str
    sender_id: str
    sender_name: str
    sender_initials: str
    body: str
    created_at: datetime
    is_own: bool
    attachments: list[MessageAttachmentView]


class CollaborationService:
    """Manage employee conversations, messages, and chat attachments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.notification_service = NotificationService()

    def list_people(
        self,
        organization_id: uuid.UUID,
        *,
        current_person_id: uuid.UUID,
        search: str | None = None,
        limit: int = 50,
    ) -> list[Person]:
        """List active people in the tenant for starting conversations."""
        org_id = coerce_uuid(organization_id)
        current_id = coerce_uuid(current_person_id)
        stmt = (
            select(Person)
            .where(
                Person.organization_id == org_id,
                Person.id != current_id,
                Person.is_active.is_(True),
                Person.status == PersonStatus.active,
            )
            .order_by(Person.display_name, Person.first_name, Person.last_name)
            .limit(limit)
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Person.display_name.ilike(pattern),
                    Person.first_name.ilike(pattern),
                    Person.last_name.ilike(pattern),
                    Person.email.ilike(pattern),
                )
            )
        return list(self.db.scalars(stmt).all())

    def list_conversations(
        self,
        organization_id: uuid.UUID,
        person_id: uuid.UUID,
        *,
        search: str | None = None,
        limit: int = 50,
    ) -> list[ConversationListItem]:
        """List conversations visible to a person."""
        org_id = coerce_uuid(organization_id)
        user_id = coerce_uuid(person_id)
        stmt = (
            select(ConversationParticipant)
            .join(Conversation)
            .options(
                selectinload(ConversationParticipant.conversation).selectinload(
                    Conversation.participants
                ),
                selectinload(ConversationParticipant.conversation).selectinload(
                    Conversation.messages
                ),
            )
            .where(
                ConversationParticipant.organization_id == org_id,
                ConversationParticipant.person_id == user_id,
                ConversationParticipant.is_archived.is_(False),
                Conversation.organization_id == org_id,
                Conversation.is_archived.is_(False),
            )
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Conversation.title.ilike(pattern),
                    Conversation.description.ilike(pattern),
                )
            )

        participants = list(self.db.scalars(stmt).all())
        return [
            self._format_conversation_item(participant, user_id)
            for participant in participants
        ]

    def get_conversation_for_member(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | str,
        person_id: uuid.UUID,
    ) -> Conversation | None:
        """Return a conversation only when the person is a member."""
        org_id = coerce_uuid(organization_id)
        conv_id = coerce_uuid(conversation_id)
        user_id = coerce_uuid(person_id)
        stmt = (
            select(Conversation)
            .join(ConversationParticipant)
            .options(
                selectinload(Conversation.participants).selectinload(
                    ConversationParticipant.person
                ),
                selectinload(Conversation.messages).selectinload(
                    ConversationMessage.attachments
                ),
            )
            .where(
                Conversation.organization_id == org_id,
                Conversation.conversation_id == conv_id,
                Conversation.is_archived.is_(False),
                ConversationParticipant.person_id == user_id,
                ConversationParticipant.is_archived.is_(False),
            )
        )
        return self.db.scalar(stmt)

    def create_direct_conversation(
        self,
        organization_id: uuid.UUID,
        creator_id: uuid.UUID,
        other_person_id: uuid.UUID | str,
    ) -> Conversation:
        """Create or return an existing direct conversation."""
        org_id = coerce_uuid(organization_id)
        creator = coerce_uuid(creator_id)
        other = coerce_uuid(other_person_id)
        if creator == other:
            raise ValueError("Choose another employee to start a conversation.")
        other_person = self._get_person(org_id, other)
        if other_person is None:
            raise ValueError("Employee not found.")

        existing = self._find_direct_conversation(org_id, creator, other)
        if existing:
            return existing

        conversation = Conversation(
            organization_id=org_id,
            conversation_type=ConversationType.DIRECT,
            title=None,
            created_by_id=creator,
        )
        self.db.add(conversation)
        self.db.flush()
        self._add_participant(conversation, creator, ParticipantRole.OWNER)
        self._add_participant(conversation, other, ParticipantRole.MEMBER)
        self.db.flush()
        return conversation

    def create_group_conversation(
        self,
        organization_id: uuid.UUID,
        creator_id: uuid.UUID,
        *,
        title: str,
        participant_ids: list[str] | list[uuid.UUID],
        description: str | None = None,
    ) -> Conversation:
        """Create a group conversation."""
        org_id = coerce_uuid(organization_id)
        creator = coerce_uuid(creator_id)
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Group name is required.")

        members = {creator}
        for value in participant_ids:
            if value:
                members.add(coerce_uuid(value))

        if len(members) < 2:
            raise ValueError("Add at least one employee to the group.")

        found = self._valid_person_ids(org_id, members)
        missing = members - found
        if missing:
            raise ValueError("One or more selected employees could not be found.")

        conversation = Conversation(
            organization_id=org_id,
            conversation_type=ConversationType.GROUP,
            title=clean_title[:160],
            description=(description or "").strip() or None,
            created_by_id=creator,
        )
        self.db.add(conversation)
        self.db.flush()
        for member_id in sorted(members, key=str):
            role = ParticipantRole.OWNER if member_id == creator else ParticipantRole.MEMBER
            self._add_participant(conversation, member_id, role)
        self.db.flush()
        return conversation

    async def add_message(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | str,
        sender_id: uuid.UUID,
        *,
        body: str,
        files: list[UploadFile] | None = None,
    ) -> ConversationMessage:
        """Add a message and optional attachments."""
        org_id = coerce_uuid(organization_id)
        sender = coerce_uuid(sender_id)
        conversation = self.get_conversation_for_member(org_id, conversation_id, sender)
        if conversation is None:
            raise ValueError("Conversation not found.")

        clean_body = body.strip()
        active_files = [
            file
            for file in (files or [])
            if file is not None and getattr(file, "filename", None)
        ]
        if not clean_body and not active_files:
            raise ValueError("Message or attachment is required.")

        message = ConversationMessage(
            organization_id=org_id,
            conversation_id=conversation.conversation_id,
            sender_id=sender,
            body=clean_body or "Shared an attachment.",
        )
        self.db.add(message)
        self.db.flush()

        for file in active_files:
            await self._save_attachment(org_id, message, sender, file)

        conversation.updated_at = datetime.now(timezone.utc)
        self.mark_read(org_id, conversation.conversation_id, sender)
        self._notify_participants(org_id, conversation, message, sender)
        self.db.flush()
        return message

    def list_messages(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | str,
        person_id: uuid.UUID,
        *,
        limit: int = 100,
    ) -> list[MessageView]:
        """List recent messages in a conversation."""
        org_id = coerce_uuid(organization_id)
        user_id = coerce_uuid(person_id)
        conversation = self.get_conversation_for_member(org_id, conversation_id, user_id)
        if conversation is None:
            return []
        stmt = (
            select(ConversationMessage)
            .options(
                selectinload(ConversationMessage.sender),
                selectinload(ConversationMessage.attachments),
            )
            .where(
                ConversationMessage.organization_id == org_id,
                ConversationMessage.conversation_id == conversation.conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(self.db.scalars(stmt).all())
        messages.reverse()
        return [self._format_message(message, user_id) for message in messages]

    def mark_read(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID | str,
        person_id: uuid.UUID,
    ) -> None:
        """Mark a conversation as read for a participant."""
        org_id = coerce_uuid(organization_id)
        conv_id = coerce_uuid(conversation_id)
        user_id = coerce_uuid(person_id)
        participant = self.db.scalar(
            select(ConversationParticipant).where(
                ConversationParticipant.organization_id == org_id,
                ConversationParticipant.conversation_id == conv_id,
                ConversationParticipant.person_id == user_id,
            )
        )
        if participant:
            participant.last_read_at = datetime.now(timezone.utc)
            self.db.flush()

    def get_attachment_for_member(
        self,
        organization_id: uuid.UUID,
        attachment_id: uuid.UUID | str,
        person_id: uuid.UUID,
    ) -> ConversationAttachment | None:
        """Return an attachment only when the user belongs to the conversation."""
        org_id = coerce_uuid(organization_id)
        att_id = coerce_uuid(attachment_id)
        user_id = coerce_uuid(person_id)
        stmt = (
            select(ConversationAttachment)
            .join(ConversationMessage)
            .join(Conversation)
            .join(ConversationParticipant)
            .where(
                ConversationAttachment.organization_id == org_id,
                ConversationAttachment.attachment_id == att_id,
                ConversationMessage.organization_id == org_id,
                Conversation.organization_id == org_id,
                ConversationParticipant.organization_id == org_id,
                ConversationParticipant.person_id == user_id,
                ConversationParticipant.conversation_id
                == Conversation.conversation_id,
            )
        )
        return self.db.scalar(stmt)

    def _format_conversation_item(
        self,
        participant: ConversationParticipant,
        current_person_id: uuid.UUID,
    ) -> ConversationListItem:
        conversation = participant.conversation
        last_message = self._last_message(conversation)
        title = self._conversation_title(conversation, current_person_id)
        subtitle = self._conversation_subtitle(conversation, current_person_id)
        unread = self._unread_count(participant)
        return ConversationListItem(
            conversation_id=str(conversation.conversation_id),
            title=title,
            subtitle=subtitle,
            conversation_type=conversation.conversation_type.value,
            unread_count=unread,
            participant_count=len(conversation.participants),
            last_message=(last_message.body[:120] if last_message else "No messages yet"),
            last_message_at=last_message.created_at if last_message else None,
            is_muted=participant.is_muted,
        )

    def _format_message(
        self,
        message: ConversationMessage,
        current_person_id: uuid.UUID,
    ) -> MessageView:
        sender_name = message.sender.name if message.sender else "Unknown"
        initials = "".join(part[:1].upper() for part in sender_name.split()[:2]) or "U"
        return MessageView(
            message_id=str(message.message_id),
            sender_id=str(message.sender_id),
            sender_name=sender_name,
            sender_initials=initials,
            body=message.body,
            created_at=message.created_at,
            is_own=message.sender_id == current_person_id,
            attachments=[
                MessageAttachmentView(
                    attachment_id=str(att.attachment_id),
                    filename=att.filename,
                    content_type=att.content_type,
                    file_size=format_file_size(att.file_size),
                    is_image=att.is_image,
                    download_url=f"/collaboration/attachments/{att.attachment_id}",
                )
                for att in message.attachments
            ],
        )

    def _conversation_title(
        self,
        conversation: Conversation,
        current_person_id: uuid.UUID,
    ) -> str:
        if conversation.title:
            return conversation.title
        if conversation.conversation_type == ConversationType.DIRECT:
            for participant in conversation.participants:
                if participant.person_id != current_person_id and participant.person:
                    return participant.person.name
            return "Direct message"
        if conversation.project:
            return getattr(conversation.project, "project_name", None) or "Project chat"
        return "Group chat"

    def _conversation_subtitle(
        self,
        conversation: Conversation,
        current_person_id: uuid.UUID,
    ) -> str:
        people = [
            participant.person.name
            for participant in conversation.participants
            if participant.person and participant.person_id != current_person_id
        ]
        if conversation.conversation_type == ConversationType.DIRECT:
            return people[0] if people else "Direct message"
        if len(people) <= 3:
            return ", ".join(people) if people else "No other members"
        return f"{', '.join(people[:3])} +{len(people) - 3} more"

    def _last_message(self, conversation: Conversation) -> ConversationMessage | None:
        return self.db.scalar(
            select(ConversationMessage)
            .where(
                ConversationMessage.organization_id == conversation.organization_id,
                ConversationMessage.conversation_id == conversation.conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(1)
        )

    def _unread_count(self, participant: ConversationParticipant) -> int:
        stmt = select(func.count(ConversationMessage.message_id)).where(
            ConversationMessage.organization_id == participant.organization_id,
            ConversationMessage.conversation_id == participant.conversation_id,
            ConversationMessage.sender_id != participant.person_id,
            ConversationMessage.is_deleted.is_(False),
        )
        if participant.last_read_at is not None:
            stmt = stmt.where(ConversationMessage.created_at > participant.last_read_at)
        return int(self.db.scalar(stmt) or 0)

    def _get_person(self, organization_id: uuid.UUID, person_id: uuid.UUID) -> Person | None:
        return self.db.scalar(
            select(Person).where(
                Person.organization_id == organization_id,
                Person.id == person_id,
                Person.is_active.is_(True),
            )
        )

    def _valid_person_ids(
        self,
        organization_id: uuid.UUID,
        person_ids: set[uuid.UUID],
    ) -> set[uuid.UUID]:
        if not person_ids:
            return set()
        stmt = select(Person.id).where(
            Person.organization_id == organization_id,
            Person.id.in_(person_ids),
            Person.is_active.is_(True),
        )
        return set(self.db.scalars(stmt).all())

    def _find_direct_conversation(
        self,
        organization_id: uuid.UUID,
        creator_id: uuid.UUID,
        other_person_id: uuid.UUID,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .join(ConversationParticipant)
            .options(selectinload(Conversation.participants))
            .where(
                Conversation.organization_id == organization_id,
                Conversation.conversation_type == ConversationType.DIRECT,
                Conversation.is_archived.is_(False),
                ConversationParticipant.person_id == creator_id,
            )
        )
        for conversation in self.db.scalars(stmt).all():
            member_ids = {participant.person_id for participant in conversation.participants}
            if {creator_id, other_person_id}.issubset(member_ids):
                return conversation
        return None

    def _add_participant(
        self,
        conversation: Conversation,
        person_id: uuid.UUID,
        role: ParticipantRole,
    ) -> ConversationParticipant:
        participant = ConversationParticipant(
            organization_id=conversation.organization_id,
            conversation_id=conversation.conversation_id,
            person_id=person_id,
            role=role,
        )
        self.db.add(participant)
        return participant

    async def _save_attachment(
        self,
        organization_id: uuid.UUID,
        message: ConversationMessage,
        uploaded_by_id: uuid.UUID,
        file: UploadFile,
    ) -> ConversationAttachment:
        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("Attached files cannot be empty.")
        upload_service = get_collaboration_attachment_upload()
        try:
            upload_result = upload_service.save(
                file_bytes,
                content_type=file.content_type or "application/octet-stream",
                subdirs=(str(organization_id), str(message.conversation_id)),
                original_filename=file.filename or "attachment",
            )
        except FileUploadError as exc:
            raise ValueError(str(exc)) from exc
        attachment = ConversationAttachment(
            organization_id=organization_id,
            message_id=message.message_id,
            uploaded_by_id=uploaded_by_id,
            filename=file.filename or upload_result.filename,
            storage_path=upload_result.relative_path,
            content_type=file.content_type or "application/octet-stream",
            file_size=upload_result.file_size,
            checksum=upload_result.checksum,
        )
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def _notify_participants(
        self,
        organization_id: uuid.UUID,
        conversation: Conversation,
        message: ConversationMessage,
        sender_id: uuid.UUID,
    ) -> None:
        sender_name = message.sender.name if message.sender else "Someone"
        title = self._conversation_title(conversation, sender_id)
        for participant in conversation.participants:
            if participant.person_id == sender_id or participant.is_muted:
                continue
            self.notification_service.create(
                self.db,
                organization_id=organization_id,
                recipient_id=participant.person_id,
                entity_type=EntityType.SYSTEM,
                entity_id=message.message_id,
                notification_type=NotificationType.COMMENT,
                title=f"New message in {title}",
                message=f"{sender_name}: {message.body[:120]}",
                action_url=f"/collaboration?conversation_id={conversation.conversation_id}",
                actor_id=sender_id,
            )


collaboration_service = CollaborationService
