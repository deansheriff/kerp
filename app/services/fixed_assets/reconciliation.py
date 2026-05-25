"""Fixed asset depreciation to GL reconciliation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.finance.gl.journal_entry import JournalEntry, JournalStatus
from app.models.finance.gl.journal_entry_line import JournalEntryLine
from app.models.fixed_assets.depreciation_run import (
    DepreciationRun,
    DepreciationRunStatus,
)
from app.models.fixed_assets.depreciation_schedule import DepreciationSchedule
from app.services.common import coerce_uuid


DEFAULT_RECONCILIATION_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class DepreciationGLReconciliationLine:
    """One expected-vs-actual GL comparison for a depreciation run."""

    account_id: UUID
    side: str
    expected_amount: Decimal
    gl_amount: Decimal
    variance: Decimal
    status: str


@dataclass(frozen=True)
class DepreciationGLReconciliationResult:
    """Summary of depreciation run reconciliation against GL lines."""

    run_id: UUID
    organization_id: UUID
    status: str
    is_reconciled: bool
    matched_count: int
    variance_count: int
    missing_gl_count: int
    extra_gl_count: int
    expected_total: Decimal
    gl_total: Decimal
    net_variance: Decimal
    lines: list[DepreciationGLReconciliationLine]

    def as_dict(self) -> dict[str, object]:
        """Return a Celery/result friendly representation."""
        return {
            "run_id": str(self.run_id),
            "organization_id": str(self.organization_id),
            "status": self.status,
            "is_reconciled": self.is_reconciled,
            "matched_count": self.matched_count,
            "variance_count": self.variance_count,
            "missing_gl_count": self.missing_gl_count,
            "extra_gl_count": self.extra_gl_count,
            "expected_total": str(self.expected_total),
            "gl_total": str(self.gl_total),
            "net_variance": str(self.net_variance),
            "lines": [
                {
                    "account_id": str(line.account_id),
                    "side": line.side,
                    "expected_amount": str(line.expected_amount),
                    "gl_amount": str(line.gl_amount),
                    "variance": str(line.variance),
                    "status": line.status,
                }
                for line in self.lines
            ],
        }


class FixedAssetDepreciationReconciliationService:
    """Compare a depreciation run's calculated schedules to posted GL evidence."""

    EXPENSE_SIDE = "DEBIT_EXPENSE"
    ACCUMULATED_DEPRECIATION_SIDE = "CREDIT_ACCUMULATED_DEPRECIATION"

    @staticmethod
    def reconcile_run(
        db: Session,
        organization_id: UUID,
        run_id: UUID,
        *,
        tolerance: Decimal = DEFAULT_RECONCILIATION_TOLERANCE,
    ) -> DepreciationGLReconciliationResult:
        """Auto-match safe depreciation lines and flag real differences.

        This method does not post correction journals or force balances to agree.
        It only compares the run schedules with the posted FA depreciation journal.
        """
        org_id = coerce_uuid(organization_id)
        r_id = coerce_uuid(run_id)

        run = db.get(DepreciationRun, r_id)
        if not run or run.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Depreciation run not found")

        if run.status not in {
            DepreciationRunStatus.POSTED,
            DepreciationRunStatus.REVERSED,
        }:
            raise HTTPException(
                status_code=400,
                detail="Depreciation run must be posted before GL reconciliation",
            )

        expected = FixedAssetDepreciationReconciliationService._expected_amounts(
            db, r_id
        )
        actual = FixedAssetDepreciationReconciliationService._posted_gl_amounts(
            db, org_id, run
        )

        lines: list[DepreciationGLReconciliationLine] = []
        for key in sorted(expected.keys() | actual.keys(), key=lambda item: str(item)):
            account_id, side = key
            expected_amount = expected.get(key, Decimal("0"))
            gl_amount = actual.get(key, Decimal("0"))
            variance = expected_amount - gl_amount
            status = FixedAssetDepreciationReconciliationService._line_status(
                expected_amount,
                gl_amount,
                variance,
                tolerance,
            )
            lines.append(
                DepreciationGLReconciliationLine(
                    account_id=account_id,
                    side=side,
                    expected_amount=expected_amount,
                    gl_amount=gl_amount,
                    variance=variance,
                    status=status,
                )
            )

        matched_count = sum(1 for line in lines if line.status == "MATCHED")
        variance_count = sum(1 for line in lines if line.status == "VARIANCE")
        missing_gl_count = sum(1 for line in lines if line.status == "MISSING_GL")
        extra_gl_count = sum(1 for line in lines if line.status == "EXTRA_GL")
        expected_total = sum((line.expected_amount for line in lines), Decimal("0"))
        gl_total = sum((line.gl_amount for line in lines), Decimal("0"))
        net_variance = expected_total - gl_total
        is_reconciled = bool(lines) and all(line.status == "MATCHED" for line in lines)

        return DepreciationGLReconciliationResult(
            run_id=r_id,
            organization_id=org_id,
            status="reconciled" if is_reconciled else "review_required",
            is_reconciled=is_reconciled,
            matched_count=matched_count,
            variance_count=variance_count,
            missing_gl_count=missing_gl_count,
            extra_gl_count=extra_gl_count,
            expected_total=expected_total,
            gl_total=gl_total,
            net_variance=net_variance,
            lines=lines,
        )

    @staticmethod
    def _expected_amounts(
        db: Session,
        run_id: UUID,
    ) -> dict[tuple[UUID, str], Decimal]:
        expected: dict[tuple[UUID, str], Decimal] = {}
        schedules = db.scalars(
            select(DepreciationSchedule).where(DepreciationSchedule.run_id == run_id)
        ).all()
        for schedule in schedules:
            amount = Decimal(str(schedule.depreciation_amount or 0))
            if amount <= 0:
                continue
            expense_key = (
                schedule.expense_account_id,
                FixedAssetDepreciationReconciliationService.EXPENSE_SIDE,
            )
            accum_key = (
                schedule.accumulated_depreciation_account_id,
                FixedAssetDepreciationReconciliationService.ACCUMULATED_DEPRECIATION_SIDE,
            )
            expected[expense_key] = expected.get(expense_key, Decimal("0")) + amount
            expected[accum_key] = expected.get(accum_key, Decimal("0")) + amount
        return expected

    @staticmethod
    def _posted_gl_amounts(
        db: Session,
        organization_id: UUID,
        run: DepreciationRun,
    ) -> dict[tuple[UUID, str], Decimal]:
        actual: dict[tuple[UUID, str], Decimal] = {}
        source_filter = and_(
            JournalEntry.source_module == "FA",
            JournalEntry.source_document_type == "DEPRECIATION_RUN",
            JournalEntry.source_document_id == run.run_id,
        )
        if run.journal_entry_id:
            source_filter = or_(
                JournalEntry.journal_entry_id == run.journal_entry_id,
                source_filter,
            )

        rows = db.execute(
            select(
                JournalEntryLine.account_id,
                JournalEntryLine.debit_amount_functional,
                JournalEntryLine.credit_amount_functional,
            )
            .join(
                JournalEntry,
                JournalEntry.journal_entry_id == JournalEntryLine.journal_entry_id,
            )
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalStatus.POSTED,
                source_filter,
            )
        ).all()

        for row in rows:
            debit_amount = Decimal(str(row.debit_amount_functional or 0))
            credit_amount = Decimal(str(row.credit_amount_functional or 0))
            if debit_amount > 0:
                key = (
                    row.account_id,
                    FixedAssetDepreciationReconciliationService.EXPENSE_SIDE,
                )
                actual[key] = actual.get(key, Decimal("0")) + debit_amount
            if credit_amount > 0:
                key = (
                    row.account_id,
                    FixedAssetDepreciationReconciliationService.ACCUMULATED_DEPRECIATION_SIDE,
                )
                actual[key] = actual.get(key, Decimal("0")) + credit_amount
        return actual

    @staticmethod
    def _line_status(
        expected_amount: Decimal,
        gl_amount: Decimal,
        variance: Decimal,
        tolerance: Decimal,
    ) -> str:
        if expected_amount == 0 and gl_amount > 0:
            return "EXTRA_GL"
        if expected_amount > 0 and gl_amount == 0:
            return "MISSING_GL"
        if variance.copy_abs() <= tolerance:
            return "MATCHED"
        return "VARIANCE"


fa_depreciation_reconciliation_service = FixedAssetDepreciationReconciliationService()
