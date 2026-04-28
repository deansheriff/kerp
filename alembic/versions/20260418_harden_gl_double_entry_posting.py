"""Harden GL double-entry posting idempotency.

Revision ID: 20260418_harden_gl_posting
Revises: 20260415_add_statement_line_number_uniqueness, 20260416_add_fa_asset_current_depreciation_schedule_column, f8c4a2c1e9bf
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_harden_gl_posting"
down_revision = (
    "20260415_add_statement_line_number_uniqueness",
    "20260416_add_fa_asset_current_depreciation_schedule_column",
    "f8c4a2c1e9bf",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    posting_batch_columns = {
        col["name"] for col in insp.get_columns("posting_batch", schema="gl")
    }
    posting_batch_fks = insp.get_foreign_keys("posting_batch", schema="gl")
    posting_batch_unique_constraints = {
        constraint["name"]
        for constraint in insp.get_unique_constraints("posting_batch", schema="gl")
        if constraint.get("name")
    }
    posted_ledger_line_unique_constraints = {
        constraint["name"]
        for constraint in insp.get_unique_constraints("posted_ledger_line", schema="gl")
        if constraint.get("name")
    }
    journal_entry_line_checks = {
        constraint["name"]
        for constraint in insp.get_check_constraints("journal_entry_line", schema="gl")
        if constraint.get("name")
    }
    posted_ledger_line_checks = {
        constraint["name"]
        for constraint in insp.get_check_constraints("posted_ledger_line", schema="gl")
        if constraint.get("name")
    }

    if "journal_entry_id" not in posting_batch_columns:
        op.add_column(
            "posting_batch",
            sa.Column(
                "journal_entry_id",
                sa.UUID(),
                nullable=True,
                comment="Journal entry this idempotency key posted",
            ),
            schema="gl",
        )

    has_journal_entry_fk = any(
        fk.get("referred_table") == "journal_entry"
        and fk.get("constrained_columns") == ["journal_entry_id"]
        for fk in posting_batch_fks
    )

    op.execute(
        """
        UPDATE gl.posting_batch pb
        SET journal_entry_id = x.journal_entry_id
        FROM (
            SELECT
                posting_batch_id,
                MIN(journal_entry_id::text)::uuid AS journal_entry_id
            FROM gl.posted_ledger_line
            GROUP BY posting_batch_id
            HAVING COUNT(DISTINCT journal_entry_id) = 1
        ) x
        WHERE pb.batch_id = x.posting_batch_id
          AND pb.journal_entry_id IS NULL
        """
    )

    if not has_journal_entry_fk:
        op.execute(
            """
            ALTER TABLE gl.posting_batch
            ADD CONSTRAINT fk_posting_batch_journal_entry_id
            FOREIGN KEY (journal_entry_id)
            REFERENCES gl.journal_entry (journal_entry_id)
            NOT VALID
            """
        )

    if "uq_batch_org_idempotency" not in posting_batch_unique_constraints:
        if "uq_batch_idempotency" in posting_batch_unique_constraints:
            op.drop_constraint("uq_batch_idempotency", "posting_batch", schema="gl")
        op.create_unique_constraint(
            "uq_batch_org_idempotency",
            "posting_batch",
            ["organization_id", "idempotency_key"],
            schema="gl",
        )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM gl.posted_ledger_line
                GROUP BY journal_entry_id, journal_line_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot add uq_pll_journal_line_once: duplicate posted ledger journal lines exist';
            END IF;
        END $$;
        """
    )
    if "uq_pll_journal_line_once" not in posted_ledger_line_unique_constraints:
        op.create_unique_constraint(
            "uq_pll_journal_line_once",
            "posted_ledger_line",
            ["journal_entry_id", "journal_line_id"],
            schema="gl",
        )

    if "ck_jel_amounts_non_negative" not in journal_entry_line_checks:
        op.create_check_constraint(
            "ck_jel_amounts_non_negative",
            "journal_entry_line",
            "debit_amount >= 0 AND credit_amount >= 0",
            schema="gl",
        )
    if "ck_jel_functional_amounts_non_negative" not in journal_entry_line_checks:
        op.create_check_constraint(
            "ck_jel_functional_amounts_non_negative",
            "journal_entry_line",
            "debit_amount_functional >= 0 AND credit_amount_functional >= 0",
            schema="gl",
        )
    if "ck_jel_exactly_one_amount" not in journal_entry_line_checks:
        op.create_check_constraint(
            "ck_jel_exactly_one_amount",
            "journal_entry_line",
            "((debit_amount > 0 AND credit_amount = 0) OR "
            "(debit_amount = 0 AND credit_amount > 0))",
            schema="gl",
        )
    if "ck_jel_exactly_one_functional_amount" not in journal_entry_line_checks:
        op.create_check_constraint(
            "ck_jel_exactly_one_functional_amount",
            "journal_entry_line",
            "((debit_amount_functional > 0 AND credit_amount_functional = 0) OR "
            "(debit_amount_functional = 0 AND credit_amount_functional > 0))",
            schema="gl",
        )

    if "ck_pll_amounts_non_negative" not in posted_ledger_line_checks:
        op.create_check_constraint(
            "ck_pll_amounts_non_negative",
            "posted_ledger_line",
            "debit_amount >= 0 AND credit_amount >= 0",
            schema="gl",
        )
    if "ck_pll_exactly_one_amount" not in posted_ledger_line_checks:
        op.create_check_constraint(
            "ck_pll_exactly_one_amount",
            "posted_ledger_line",
            "((debit_amount > 0 AND credit_amount = 0) OR "
            "(debit_amount = 0 AND credit_amount > 0))",
            schema="gl",
        )

    if not has_journal_entry_fk:
        op.execute(
            """
            ALTER TABLE gl.posting_batch
            VALIDATE CONSTRAINT fk_posting_batch_journal_entry_id
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    posting_batch_unique_constraints = {
        constraint["name"]
        for constraint in insp.get_unique_constraints("posting_batch", schema="gl")
        if constraint.get("name")
    }
    posted_ledger_line_unique_constraints = {
        constraint["name"]
        for constraint in insp.get_unique_constraints("posted_ledger_line", schema="gl")
        if constraint.get("name")
    }
    journal_entry_line_checks = {
        constraint["name"]
        for constraint in insp.get_check_constraints("journal_entry_line", schema="gl")
        if constraint.get("name")
    }
    posted_ledger_line_checks = {
        constraint["name"]
        for constraint in insp.get_check_constraints("posted_ledger_line", schema="gl")
        if constraint.get("name")
    }

    if "ck_pll_exactly_one_amount" in posted_ledger_line_checks:
        op.drop_constraint(
            "ck_pll_exactly_one_amount",
            "posted_ledger_line",
            schema="gl",
            type_="check",
        )
    if "ck_pll_amounts_non_negative" in posted_ledger_line_checks:
        op.drop_constraint(
            "ck_pll_amounts_non_negative",
            "posted_ledger_line",
            schema="gl",
            type_="check",
        )
    if "ck_jel_exactly_one_functional_amount" in journal_entry_line_checks:
        op.drop_constraint(
            "ck_jel_exactly_one_functional_amount",
            "journal_entry_line",
            schema="gl",
            type_="check",
        )
    if "ck_jel_exactly_one_amount" in journal_entry_line_checks:
        op.drop_constraint(
            "ck_jel_exactly_one_amount",
            "journal_entry_line",
            schema="gl",
            type_="check",
        )
    if "ck_jel_functional_amounts_non_negative" in journal_entry_line_checks:
        op.drop_constraint(
            "ck_jel_functional_amounts_non_negative",
            "journal_entry_line",
            schema="gl",
            type_="check",
        )
    if "ck_jel_amounts_non_negative" in journal_entry_line_checks:
        op.drop_constraint(
            "ck_jel_amounts_non_negative",
            "journal_entry_line",
            schema="gl",
            type_="check",
        )
    if "uq_pll_journal_line_once" in posted_ledger_line_unique_constraints:
        op.drop_constraint(
            "uq_pll_journal_line_once",
            "posted_ledger_line",
            schema="gl",
            type_="unique",
        )
    if "uq_batch_org_idempotency" in posting_batch_unique_constraints:
        op.drop_constraint(
            "uq_batch_org_idempotency",
            "posting_batch",
            schema="gl",
            type_="unique",
        )
    if "uq_batch_idempotency" not in posting_batch_unique_constraints:
        op.create_unique_constraint(
            "uq_batch_idempotency",
            "posting_batch",
            ["idempotency_key"],
            schema="gl",
        )
