"""
Notification helpers for the Collaboration module.

Uses the existing NotificationService to create in-app notifications
for messaging events.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.notification import EntityType, NotificationChannel, NotificationType
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

_notif_service = NotificationService()


def notify_new_message(
    db: Session,
    org_id: uuid.UUID,
    message,
    conversation,
    participant_ids: list[uuid.UUID],
) -> None:
    """Create notifications for a new message (all participants except sender)."""
    sender_name = "Someone"
    if message.sender:
        first = getattr(message.sender, "first_name", "") or ""
        last = getattr(message.sender, "last_name", "") or ""
        sender_name = f"{first} {last}".strip() or "Someone"

    conv_name = conversation.name or "Direct Message"
    content_preview = (message.content or "sent a file")[:80]

    for pid in participant_ids:
        if pid == message.sender_id:
            continue

        try:
            _notif_service.create(
                db,
                organization_id=org_id,
                recipient_id=pid,
                entity_type=EntityType.COLLABORATION,
                entity_id=conversation.conversation_id,
                notification_type=NotificationType.COMMENT,
                title=f"{sender_name} in {conv_name}",
                message=content_preview,
                action_url=f"/collaboration/c/{conversation.conversation_id}",
                actor_id=message.sender_id,
            )
        except Exception:
            logger.debug("Failed to create notification for %s", pid, exc_info=True)


def notify_mention(
    db: Session,
    org_id: uuid.UUID,
    message,
    conversation,
    mentioned_ids: list[uuid.UUID],
) -> None:
    """Create MENTION notifications (higher priority)."""
    sender_name = "Someone"
    if message.sender:
        first = getattr(message.sender, "first_name", "") or ""
        last = getattr(message.sender, "last_name", "") or ""
        sender_name = f"{first} {last}".strip() or "Someone"

    conv_name = conversation.name or "Direct Message"

    for pid in mentioned_ids:
        if pid == message.sender_id:
            continue

        try:
            _notif_service.create(
                db,
                organization_id=org_id,
                recipient_id=pid,
                entity_type=EntityType.COLLABORATION,
                entity_id=conversation.conversation_id,
                notification_type=NotificationType.MENTION,
                title=f"{sender_name} mentioned you in {conv_name}",
                message=(message.content or "")[:80],
                channel=NotificationChannel.BOTH,
                action_url=f"/collaboration/c/{conversation.conversation_id}",
                actor_id=message.sender_id,
            )
        except Exception:
            logger.debug("Failed to create mention notification for %s", pid, exc_info=True)


def notify_added_to_group(
    db: Session,
    org_id: uuid.UUID,
    conversation,
    added_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
) -> None:
    """Notify people they were added to a group conversation."""
    conv_name = conversation.name or "a group"

    for pid in added_ids:
        if pid == actor_id:
            continue

        try:
            _notif_service.create(
                db,
                organization_id=org_id,
                recipient_id=pid,
                entity_type=EntityType.COLLABORATION,
                entity_id=conversation.conversation_id,
                notification_type=NotificationType.ASSIGNED,
                title=f"Added to {conv_name}",
                message=f"You were added to the conversation '{conv_name}'.",
                action_url=f"/collaboration/c/{conversation.conversation_id}",
                actor_id=actor_id,
            )
        except Exception:
            logger.debug("Failed to create add-to-group notification for %s", pid, exc_info=True)
