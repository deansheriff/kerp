"""Collaboration models."""

from app.models.collaboration.attachment import MessageAttachment
from app.models.collaboration.conversation import Conversation, ConversationType
from app.models.collaboration.mention import MessageMention
from app.models.collaboration.message import Message, MessageType
from app.models.collaboration.participant import (
    ConversationParticipant,
    ParticipantRole,
)
from app.models.collaboration.reaction import MessageReaction

ConversationAttachment = MessageAttachment
ConversationMessage = Message

__all__ = [
    "Conversation",
    "ConversationAttachment",
    "ConversationMessage",
    "ConversationParticipant",
    "ConversationType",
    "Message",
    "MessageAttachment",
    "MessageMention",
    "MessageReaction",
    "MessageType",
    "ParticipantRole",
]
