import asyncio
import uuid
from unittest.mock import patch

from sqlalchemy import select

from app.models.collaboration import ConversationParticipant, ConversationType
from app.models.person import Person
from app.services.collaboration import CollaborationService
from tests.conftest import DEFAULT_TEST_ORG_ID


def _person(db_session, first_name: str, last_name: str) -> Person:
    person = Person(
        first_name=first_name,
        last_name=last_name,
        display_name=f"{first_name} {last_name}",
        email=f"{first_name.lower()}.{last_name.lower()}.{uuid.uuid4().hex[:8]}@example.com",
        organization_id=DEFAULT_TEST_ORG_ID,
    )
    db_session.add(person)
    db_session.commit()
    db_session.refresh(person)
    return person


def test_direct_conversation_is_reused_and_scoped_to_members(db_session):
    alice = _person(db_session, "Alice", "Admin")
    ben = _person(db_session, "Ben", "Builder")
    chika = _person(db_session, "Chika", "Clerk")
    service = CollaborationService(db_session)

    conversation = service.create_direct_conversation(
        DEFAULT_TEST_ORG_ID, alice.id, ben.id
    )
    same_conversation = service.create_direct_conversation(
        DEFAULT_TEST_ORG_ID, alice.id, ben.id
    )

    assert conversation.conversation_id == same_conversation.conversation_id
    assert conversation.conversation_type == ConversationType.DIRECT
    assert service.get_conversation_for_member(
        DEFAULT_TEST_ORG_ID, conversation.conversation_id, alice.id
    )
    assert service.get_conversation_for_member(
        DEFAULT_TEST_ORG_ID, conversation.conversation_id, chika.id
    ) is None


def test_group_conversation_adds_owner_and_members(db_session):
    alice = _person(db_session, "Alice", "Admin")
    ben = _person(db_session, "Ben", "Builder")
    chika = _person(db_session, "Chika", "Clerk")
    service = CollaborationService(db_session)

    conversation = service.create_group_conversation(
        DEFAULT_TEST_ORG_ID,
        alice.id,
        title="Operations",
        participant_ids=[str(ben.id), str(chika.id)],
    )

    participants = db_session.scalars(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation.conversation_id
        )
    ).all()
    members = {participant.person_id for participant in participants}
    assert members == {alice.id, ben.id, chika.id}


def test_message_marks_sender_read_and_recipient_unread(db_session):
    alice = _person(db_session, "Alice", "Admin")
    ben = _person(db_session, "Ben", "Builder")
    service = CollaborationService(db_session)
    conversation = service.create_direct_conversation(
        DEFAULT_TEST_ORG_ID, alice.id, ben.id
    )

    with patch("app.services.collaboration.NotificationService.create"):
        asyncio.run(
            service.add_message(
                DEFAULT_TEST_ORG_ID,
                conversation.conversation_id,
                alice.id,
                body="Please review the payroll schedule.",
            )
        )

    alice_items = service.list_conversations(DEFAULT_TEST_ORG_ID, alice.id)
    ben_items = service.list_conversations(DEFAULT_TEST_ORG_ID, ben.id)

    assert alice_items[0].unread_count == 0
    assert ben_items[0].unread_count == 1
    assert ben_items[0].last_message == "Please review the payroll schedule."
