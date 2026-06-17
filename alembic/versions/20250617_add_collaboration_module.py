"""add collaboration module

Revision ID: 20250617_collab
Revises:
Create Date: 2025-06-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250617_collab"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create schema
    op.execute("CREATE SCHEMA IF NOT EXISTS collab")

    # Add COLLABORATION to entity_type enum if not present
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'COLLABORATION'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'entitytype')
            ) THEN
                ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'COLLABORATION';
            END IF;
        EXCEPTION WHEN others THEN
            NULL;
        END $$;
    """)

    # conversation
    op.create_table(
        "conversation",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("core_org.organization.organization_id"), nullable=False),
        sa.Column("conversation_type", sa.Enum("DIRECT", "GROUP", "CHANNEL",
                  name="conversationtype", schema="collab"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("avatar_key", sa.String(500), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("linked_entity_type", sa.String(80), nullable=True),
        sa.Column("linked_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="collab",
    )
    op.create_index("ix_collab_conv_org", "conversation", ["organization_id"], schema="collab")
    op.create_index("ix_collab_conv_org_type", "conversation",
                    ["organization_id", "conversation_type"], schema="collab")
    op.create_index("ix_collab_conv_linked", "conversation",
                    ["linked_entity_type", "linked_entity_id"], schema="collab")

    # conversation_participant
    op.create_table(
        "conversation_participant",
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=False),
        sa.Column("role", sa.Enum("MEMBER", "ADMIN", "OWNER",
                  name="participantrole", schema="collab"), nullable=False,
                  server_default="MEMBER"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_muted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_read_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("conversation_id", "person_id", name="uq_collab_participant"),
        schema="collab",
    )
    op.create_index("ix_collab_part_conv", "conversation_participant",
                    ["conversation_id"], schema="collab")
    op.create_index("ix_collab_part_person", "conversation_participant",
                    ["person_id"], schema="collab")

    # message
    op.create_table(
        "message",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("core_org.organization.organization_id"), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("message_type", sa.Enum("TEXT", "SYSTEM", "FILE_ONLY",
                  name="messagetype", schema="collab"), nullable=False,
                  server_default="TEXT"),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.message.message_id"), nullable=True),
        sa.Column("quoted_message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.message.message_id"), nullable=True),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pinned_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=True),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_edited", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="collab",
    )
    op.create_index("ix_collab_msg_org", "message", ["organization_id"], schema="collab")
    op.create_index("ix_collab_msg_created", "message", ["created_at"], schema="collab")
    op.create_index("ix_collab_msg_conv_created", "message",
                    ["conversation_id", "created_at"], schema="collab")
    op.create_index("ix_collab_msg_conv_pinned", "message",
                    ["conversation_id", "is_pinned"], schema="collab")

    # message_attachment
    op.create_table(
        "message_attachment",
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.message.message_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_key", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="collab",
    )
    op.create_index("ix_collab_att_msg", "message_attachment",
                    ["message_id"], schema="collab")

    # message_mention
    op.create_table(
        "message_mention",
        sa.Column("mention_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.message.message_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("mentioned_person_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="collab",
    )
    op.create_index("ix_collab_mention_msg", "message_mention",
                    ["message_id"], schema="collab")
    op.create_index("ix_collab_mention_person", "message_mention",
                    ["mentioned_person_id"], schema="collab")

    # message_reaction
    op.create_table(
        "message_reaction",
        sa.Column("reaction_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("collab.message.message_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("people.id"), nullable=False),
        sa.Column("emoji", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("message_id", "person_id", "emoji", name="uq_collab_reaction"),
        schema="collab",
    )
    op.create_index("ix_collab_react_msg", "message_reaction",
                    ["message_id"], schema="collab")


def downgrade() -> None:
    op.drop_table("message_reaction", schema="collab")
    op.drop_table("message_mention", schema="collab")
    op.drop_table("message_attachment", schema="collab")
    op.drop_table("message", schema="collab")
    op.drop_table("conversation_participant", schema="collab")
    op.drop_table("conversation", schema="collab")
    op.execute("DROP TYPE IF EXISTS collab.conversationtype")
    op.execute("DROP TYPE IF EXISTS collab.participantrole")
    op.execute("DROP TYPE IF EXISTS collab.messagetype")
    op.execute("DROP SCHEMA IF EXISTS collab")
