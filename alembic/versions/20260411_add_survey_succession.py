"""Add employee survey and succession planning tables

Revision ID: 20260411_add_survey_succession
Revises: 20260411_add_grievance_salary_review
Create Date: 2026-04-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.alembic_utils import ensure_enum

# revision identifiers, used by Alembic.
revision = "20260411_add_survey_succession"
down_revision = "20260411_add_grievance_salary_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Some staging databases were created from early HR scripts that left
    # department/designation ids without primary-key constraints. The columns
    # are still unique and non-null, so add the missing constraints before this
    # migration creates foreign keys to them.
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('hr.department') IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
               FROM pg_constraint
               WHERE conrelid = 'hr.department'::regclass
                 AND contype = 'p'
           )
           AND NOT EXISTS (
               SELECT department_id
               FROM hr.department
               GROUP BY department_id
               HAVING department_id IS NULL OR count(*) > 1
           )
        THEN
            ALTER TABLE hr.department
            ADD CONSTRAINT department_pkey PRIMARY KEY (department_id);
        END IF;

        IF to_regclass('hr.designation') IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
               FROM pg_constraint
               WHERE conrelid = 'hr.designation'::regclass
                 AND contype = 'p'
           )
           AND NOT EXISTS (
               SELECT designation_id
               FROM hr.designation
               GROUP BY designation_id
               HAVING designation_id IS NULL OR count(*) > 1
           )
        THEN
            ALTER TABLE hr.designation
            ADD CONSTRAINT designation_pkey PRIMARY KEY (designation_id);
        END IF;
    END $$;
    """)

    # ------------------------------------------------------------------
    # Enum types (idempotent via ensure_enum)
    # ------------------------------------------------------------------
    survey_type = ensure_enum(
        bind,
        "survey_type",
        "ENGAGEMENT",
        "PULSE",
        "EXIT",
        "ONBOARDING",
        "CUSTOM",
    )
    survey_status = ensure_enum(
        bind,
        "survey_status",
        "DRAFT",
        "ACTIVE",
        "CLOSED",
        "ARCHIVED",
    )
    target_audience = ensure_enum(
        bind,
        "target_audience",
        "ALL",
        "DEPARTMENT",
        "DESIGNATION",
        "CUSTOM",
    )
    question_type = ensure_enum(
        bind,
        "question_type",
        "RATING",
        "TEXT",
        "SINGLE_CHOICE",
        "MULTIPLE_CHOICE",
        "SCALE",
        "YES_NO",
    )
    risk_level = ensure_enum(
        bind,
        "risk_level",
        "LOW",
        "MEDIUM",
        "HIGH",
    )
    impact_level = ensure_enum(
        bind,
        "impact_level",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    )
    succession_plan_status = ensure_enum(
        bind,
        "succession_plan_status",
        "DRAFT",
        "ACTIVE",
        "CLOSED",
    )
    readiness_level = ensure_enum(
        bind,
        "readiness_level",
        "READY_NOW",
        "READY_1_YEAR",
        "READY_2_YEARS",
        "DEVELOPMENT_NEEDED",
        "NOT_READY",
    )

    # ------------------------------------------------------------------
    # hr.survey
    # ------------------------------------------------------------------
    op.create_table(
        "survey",
        sa.Column(
            "survey_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core_org.organization.organization_id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("survey_type", survey_type, nullable=False),
        sa.Column("status", survey_status, nullable=False, server_default="DRAFT"),
        sa.Column("is_anonymous", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("target_audience", target_audience, nullable=False),
        sa.Column("target_filter", postgresql.JSONB, nullable=True),
        sa.Column("response_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="hr",
    )
    op.create_index(
        "ix_survey_organization_id", "survey", ["organization_id"], schema="hr"
    )
    op.create_index(
        "ix_survey_org_status", "survey", ["organization_id", "status"], schema="hr"
    )

    # ------------------------------------------------------------------
    # hr.survey_question
    # ------------------------------------------------------------------
    op.create_table(
        "survey_question",
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "survey_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.survey.survey_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core_org.organization.organization_id"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("question_type", question_type, nullable=False),
        sa.Column("options", postgresql.JSONB, nullable=True),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        schema="hr",
    )
    op.create_index(
        "ix_survey_question_organization_id",
        "survey_question",
        ["organization_id"],
        schema="hr",
    )
    op.create_index(
        "ix_survey_question_survey",
        "survey_question",
        ["survey_id", "sort_order"],
        schema="hr",
    )

    # ------------------------------------------------------------------
    # hr.survey_response
    # ------------------------------------------------------------------
    op.create_table(
        "survey_response",
        sa.Column(
            "response_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "survey_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.survey.survey_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core_org.organization.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.employee.employee_id"),
            nullable=True,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default="false"),
        schema="hr",
    )
    op.create_index(
        "ix_survey_response_organization_id",
        "survey_response",
        ["organization_id"],
        schema="hr",
    )
    op.create_index(
        "ix_survey_response_survey", "survey_response", ["survey_id"], schema="hr"
    )

    # ------------------------------------------------------------------
    # hr.survey_answer
    # ------------------------------------------------------------------
    op.create_table(
        "survey_answer",
        sa.Column(
            "answer_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "response_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.survey_response.response_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.survey_question.question_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text, nullable=True),
        sa.Column("answer_rating", sa.Integer, nullable=True),
        sa.Column("answer_choices", postgresql.JSONB, nullable=True),
        schema="hr",
    )
    op.create_index(
        "ix_survey_answer_response", "survey_answer", ["response_id"], schema="hr"
    )
    op.create_index(
        "ix_survey_answer_question", "survey_answer", ["question_id"], schema="hr"
    )

    # ------------------------------------------------------------------
    # hr.succession_plan
    # ------------------------------------------------------------------
    op.create_table(
        "succession_plan",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core_org.organization.organization_id"),
            nullable=False,
        ),
        sa.Column("position_title", sa.String(200), nullable=False),
        sa.Column(
            "designation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.designation.designation_id"),
            nullable=True,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.department.department_id"),
            nullable=True,
        ),
        sa.Column(
            "incumbent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.employee.employee_id"),
            nullable=True,
        ),
        sa.Column(
            "is_critical_role", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column("risk_of_loss", risk_level, nullable=False),
        sa.Column("impact_of_loss", impact_level, nullable=False),
        sa.Column(
            "status", succession_plan_status, nullable=False, server_default="DRAFT"
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("review_date", sa.Date, nullable=True),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="hr",
    )
    op.create_index(
        "ix_succession_plan_organization_id",
        "succession_plan",
        ["organization_id"],
        schema="hr",
    )
    op.create_index(
        "ix_succession_plan_org_status",
        "succession_plan",
        ["organization_id", "status"],
        schema="hr",
    )

    # ------------------------------------------------------------------
    # hr.succession_candidate
    # ------------------------------------------------------------------
    op.create_table(
        "succession_candidate",
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.succession_plan.plan_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core_org.organization.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr.employee.employee_id"),
            nullable=False,
        ),
        sa.Column("readiness_level", readiness_level, nullable=False),
        sa.Column("strengths", sa.Text, nullable=True),
        sa.Column("development_areas", sa.Text, nullable=True),
        sa.Column("development_actions", postgresql.JSONB, nullable=True),
        sa.Column("assessment_date", sa.Date, nullable=True),
        sa.Column("assessed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        schema="hr",
    )
    op.create_index(
        "ix_succession_candidate_organization_id",
        "succession_candidate",
        ["organization_id"],
        schema="hr",
    )
    op.create_index(
        "ix_succession_candidate_plan", "succession_candidate", ["plan_id"], schema="hr"
    )
    op.create_index(
        "ix_succession_candidate_employee",
        "succession_candidate",
        ["employee_id"],
        schema="hr",
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("succession_candidate", schema="hr")
    op.drop_table("succession_plan", schema="hr")
    op.drop_table("survey_answer", schema="hr")
    op.drop_table("survey_response", schema="hr")
    op.drop_table("survey_question", schema="hr")
    op.drop_table("survey", schema="hr")

    # Drop enum types
    bind = op.get_bind()
    for name in (
        "readiness_level",
        "succession_plan_status",
        "impact_level",
        "risk_level",
        "question_type",
        "target_audience",
        "survey_status",
        "survey_type",
    ):
        postgresql.ENUM(name=name, create_type=False).drop(bind, checkfirst=True)
