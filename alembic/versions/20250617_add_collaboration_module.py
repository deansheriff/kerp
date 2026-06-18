"""add collaboration module

Revision ID: 20250617_collab
Revises:
Create Date: 2025-06-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = "20250617_collab"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(connection, table_name, schema="collab"):
    """Check if a table exists in the given schema."""
    insp = sa_inspect(connection)
    return table_name in insp.get_table_names(schema=schema)


def _column_exists(connection, table_name, column_name, schema="collab"):
    """Check if a column exists in the given table."""
    insp = sa_inspect(connection)
    if table_name not in insp.get_table_names(schema=schema):
        return False
    return column_name in {
        column["name"] for column in insp.get_columns(table_name, schema=schema)
    }


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

    # Create enum types if not exists
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE collab.conversationtype AS ENUM ('DIRECT', 'GROUP', 'CHANNEL');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE collab.participantrole AS ENUM ('MEMBER', 'ADMIN', 'OWNER');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE collab.messagetype AS ENUM ('TEXT', 'SYSTEM', 'FILE_ONLY');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    conn = op.get_bind()

    # conversation
    if not _table_exists(conn, "conversation"):
        op.create_table(
            "conversation",
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("core_org.organization.organization_id"), nullable=False),
            sa.Column("conversation_type", sa.Enum("DIRECT", "GROUP", "CHANNEL",
                      name="conversationtype", schema="collab", create_type=False), nullable=False),
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
    else:
        op.execute(
            "ALTER TABLE collab.conversation "
            "ADD COLUMN IF NOT EXISTS name VARCHAR(255)"
        )
        if _column_exists(conn, "conversation", "title"):
            op.execute(
                "UPDATE collab.conversation SET name = title "
                "WHERE name IS NULL AND title IS NOT NULL"
            )
        op.execute(
            "ALTER TABLE collab.conversation "
            "ADD COLUMN IF NOT EXISTS avatar_key VARCHAR(500)"
        )
        op.execute(
            "ALTER TABLE collab.conversation "
            "ADD COLUMN IF NOT EXISTS linked_entity_type VARCHAR(80)"
        )
        op.execute(
            "ALTER TABLE collab.conversation "
            "ADD COLUMN IF NOT EXISTS linked_entity_id UUID"
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_conv_org ON collab.conversation (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_conv_org_type ON collab.conversation (organization_id, conversation_type)")
    if _column_exists(conn, "conversation", "linked_entity_type") and _column_exists(conn, "conversation", "linked_entity_id"):
        op.execute("CREATE INDEX IF NOT EXISTS ix_collab_conv_linked ON collab.conversation (linked_entity_type, linked_entity_id)")

    # conversation_participant
    if not _table_exists(conn, "conversation_participant"):
        op.create_table(
            "conversation_participant",
            sa.Column("participant_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("collab.conversation.conversation_id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("person_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("people.id"), nullable=False),
            sa.Column("role", sa.Enum("MEMBER", "ADMIN", "OWNER",
                      name="participantrole", schema="collab", create_type=False), nullable=False,
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
    else:
        if _column_exists(conn, "conversation_participant", "organization_id"):
            op.execute(
                "ALTER TABLE collab.conversation_participant "
                "ALTER COLUMN organization_id DROP NOT NULL"
            )
        op.execute(
            "ALTER TABLE collab.conversation_participant "
            "ADD COLUMN IF NOT EXISTS left_at TIMESTAMPTZ"
        )
        op.execute(
            "ALTER TABLE collab.conversation_participant "
            "ADD COLUMN IF NOT EXISTS last_read_message_id UUID"
        )
        op.execute(
            "ALTER TABLE collab.conversation_participant "
            "ADD COLUMN IF NOT EXISTS unread_count INTEGER NOT NULL DEFAULT 0"
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_part_conv ON collab.conversation_participant (conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_part_person ON collab.conversation_participant (person_id)")

    # message
    if not _table_exists(conn, "message"):
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
                      name="messagetype", schema="collab", create_type=False), nullable=False,
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_msg_org ON collab.message (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_msg_created ON collab.message (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_msg_conv_created ON collab.message (conversation_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_msg_conv_pinned ON collab.message (conversation_id, is_pinned)")

    # message_attachment
    if not _table_exists(conn, "message_attachment"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_att_msg ON collab.message_attachment (message_id)")

    # message_mention
    if not _table_exists(conn, "message_mention"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_mention_msg ON collab.message_mention (message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_mention_person ON collab.message_mention (mentioned_person_id)")

    # message_reaction
    if not _table_exists(conn, "message_reaction"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_collab_react_msg ON collab.message_reaction (message_id)")


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
