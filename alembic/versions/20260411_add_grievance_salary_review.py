"""Add grievance and salary_review tables to HR schema.

Revision ID: 20260411_add_grievance_salary_review
Revises: 20260411_add_mono_account_id
Create Date: 2026-04-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260411_add_grievance_salary_review"
down_revision = "20260411_add_mono_account_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Enum types (idempotent) --------------------------------------------------
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'hr' AND t.typname = 'grievance_category') THEN
                CREATE TYPE hr.grievance_category AS ENUM ('WORKPLACE','HARASSMENT','DISCRIMINATION','POLICY','COMPENSATION','MANAGEMENT','SAFETY','OTHER');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'hr' AND t.typname = 'grievance_severity') THEN
                CREATE TYPE hr.grievance_severity AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'hr' AND t.typname = 'grievance_status') THEN
                CREATE TYPE hr.grievance_status AS ENUM ('SUBMITTED','ACKNOWLEDGED','INVESTIGATING','RESOLVED','CLOSED','WITHDRAWN');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'hr' AND t.typname = 'salary_review_type') THEN
                CREATE TYPE hr.salary_review_type AS ENUM ('MERIT_INCREASE','PROMOTION','ANNUAL_REVIEW','MARKET_ADJUSTMENT','PROBATION_CONFIRMATION','DEMOTION');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'hr' AND t.typname = 'salary_review_status') THEN
                CREATE TYPE hr.salary_review_status AS ENUM ('DRAFT','SUBMITTED','APPROVED','REJECTED','APPLIED');
            END IF;
        END $$;
    """)

    # -- Grievance table ----------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS hr.grievance (
            grievance_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id     UUID NOT NULL REFERENCES core_org.organization(organization_id),
            employee_id         UUID REFERENCES hr.employee(employee_id),
            grievance_number    VARCHAR(30) NOT NULL,
            category            hr.grievance_category NOT NULL,
            severity            hr.grievance_severity NOT NULL DEFAULT 'MEDIUM',
            subject             VARCHAR(200) NOT NULL,
            description         TEXT NOT NULL,
            is_anonymous        BOOLEAN NOT NULL DEFAULT FALSE,
            status              hr.grievance_status NOT NULL DEFAULT 'SUBMITTED',
            assigned_to_id      UUID REFERENCES hr.employee(employee_id),
            resolution          TEXT,
            resolution_date     DATE,
            sla_due_date        DATE,
            is_escalated        BOOLEAN NOT NULL DEFAULT FALSE,
            escalated_to_id     UUID REFERENCES hr.employee(employee_id),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ,
            -- AuditMixin
            created_by_id       UUID REFERENCES people(id),
            updated_by_id       UUID REFERENCES people(id),
            -- StatusTrackingMixin
            status_changed_at   TIMESTAMPTZ,
            status_changed_by_id UUID REFERENCES people(id),

            CONSTRAINT uq_grievance_org_number UNIQUE (organization_id, grievance_number)
        );
    """)

    # Indexes (idempotent via IF NOT EXISTS)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_grievance_org_status ON hr.grievance (organization_id, status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_grievance_employee ON hr.grievance (employee_id);
    """)

    # -- Salary Review table ------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS hr.salary_review (
            review_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id     UUID NOT NULL REFERENCES core_org.organization(organization_id),
            employee_id         UUID NOT NULL REFERENCES hr.employee(employee_id),
            review_number       VARCHAR(30) NOT NULL,
            review_type         hr.salary_review_type NOT NULL,
            current_salary      NUMERIC(20,6) NOT NULL,
            proposed_salary     NUMERIC(20,6) NOT NULL,
            approved_salary     NUMERIC(20,6),
            currency_code       VARCHAR(3) NOT NULL DEFAULT 'NGN',
            percentage_change   NUMERIC(8,4) NOT NULL,
            effective_date      DATE NOT NULL,
            justification       TEXT NOT NULL,
            status              hr.salary_review_status NOT NULL DEFAULT 'DRAFT',
            appraisal_id        UUID,
            submitted_by_id     UUID REFERENCES people(id),
            approved_by_id      UUID REFERENCES people(id),
            approved_at         TIMESTAMPTZ,
            applied_at          TIMESTAMPTZ,
            rejection_reason    TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ,
            -- AuditMixin
            created_by_id       UUID REFERENCES people(id),
            updated_by_id       UUID REFERENCES people(id),
            -- StatusTrackingMixin
            status_changed_at   TIMESTAMPTZ,
            status_changed_by_id UUID REFERENCES people(id),

            CONSTRAINT uq_salary_review_org_number UNIQUE (organization_id, review_number)
        );
    """)

    # Indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_salary_review_org_status ON hr.salary_review (organization_id, status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_salary_review_employee ON hr.salary_review (employee_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hr.salary_review CASCADE;")
    op.execute("DROP TABLE IF EXISTS hr.grievance CASCADE;")
    op.execute("DROP TYPE IF EXISTS hr.salary_review_status;")
    op.execute("DROP TYPE IF EXISTS hr.salary_review_type;")
    op.execute("DROP TYPE IF EXISTS hr.grievance_status;")
    op.execute("DROP TYPE IF EXISTS hr.grievance_severity;")
    op.execute("DROP TYPE IF EXISTS hr.grievance_category;")
