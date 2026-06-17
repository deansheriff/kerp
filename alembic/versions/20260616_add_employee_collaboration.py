"""Add employee collaboration chat tables.

Revision ID: 20260616_add_collaboration
Revises: 20260603_add_match_state
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op


revision = "20260616_add_collaboration"
down_revision = "20260603_add_match_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS collab")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS collab.conversation (
            conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL
                REFERENCES core_org.organization(organization_id),
            conversation_type VARCHAR(20) NOT NULL DEFAULT 'GROUP',
            title VARCHAR(160),
            description TEXT,
            project_id UUID REFERENCES core_org.project(project_id),
            created_by_id UUID NOT NULL REFERENCES people(id),
            is_archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS collab.conversation_participant (
            participant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL
                REFERENCES core_org.organization(organization_id),
            conversation_id UUID NOT NULL
                REFERENCES collab.conversation(conversation_id) ON DELETE CASCADE,
            person_id UUID NOT NULL REFERENCES people(id),
            role VARCHAR(20) NOT NULL DEFAULT 'MEMBER',
            is_muted BOOLEAN NOT NULL DEFAULT FALSE,
            is_archived BOOLEAN NOT NULL DEFAULT FALSE,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_read_at TIMESTAMPTZ,
            CONSTRAINT uq_collab_participant_conversation_person
                UNIQUE (conversation_id, person_id)
        );

        CREATE TABLE IF NOT EXISTS collab.conversation_message (
            message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL
                REFERENCES core_org.organization(organization_id),
            conversation_id UUID NOT NULL
                REFERENCES collab.conversation(conversation_id) ON DELETE CASCADE,
            sender_id UUID NOT NULL REFERENCES people(id),
            parent_message_id UUID
                REFERENCES collab.conversation_message(message_id) ON DELETE SET NULL,
            body TEXT NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            edited_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS collab.conversation_attachment (
            attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL
                REFERENCES core_org.organization(organization_id),
            message_id UUID NOT NULL
                REFERENCES collab.conversation_message(message_id) ON DELETE CASCADE,
            uploaded_by_id UUID NOT NULL REFERENCES people(id),
            filename VARCHAR(255) NOT NULL,
            storage_path VARCHAR(500) NOT NULL,
            content_type VARCHAR(100) NOT NULL,
            file_size BIGINT NOT NULL,
            checksum VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_collab_conversation_org_updated
            ON collab.conversation (organization_id, updated_at);
        CREATE INDEX IF NOT EXISTS ix_collab_conversation_project
            ON collab.conversation (organization_id, project_id);
        CREATE INDEX IF NOT EXISTS ix_collab_participant_person
            ON collab.conversation_participant (organization_id, person_id);
        CREATE INDEX IF NOT EXISTS ix_collab_participant_conversation
            ON collab.conversation_participant (conversation_id);
        CREATE INDEX IF NOT EXISTS ix_collab_message_conversation_created
            ON collab.conversation_message (conversation_id, created_at);
        CREATE INDEX IF NOT EXISTS ix_collab_message_sender
            ON collab.conversation_message (organization_id, sender_id);
        CREATE INDEX IF NOT EXISTS ix_collab_attachment_message
            ON collab.conversation_attachment (message_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS collab.conversation_attachment;
        DROP TABLE IF EXISTS collab.conversation_message;
        DROP TABLE IF EXISTS collab.conversation_participant;
        DROP TABLE IF EXISTS collab.conversation;
        DROP SCHEMA IF EXISTS collab;
        """
    )
