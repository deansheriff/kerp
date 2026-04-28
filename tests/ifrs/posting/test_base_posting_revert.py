"""Test that BasePostingAdapter.post_to_ledger reverts the journal to DRAFT
when LedgerPostingService.post_journal_entry rejects the post.

Regression test for: 429 BANK_FEE journals stranded in APPROVED status
after an auto-reconciliation run where the period was closed at the time
of posting. The handler-level fix is to make the adapter undo its own
approve when posting fails, so no journal can remain APPROVED but unposted.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.finance.gl.journal_entry import JournalStatus
from app.services.finance.posting.base import BasePostingAdapter


def _journal_stub(status: JournalStatus = JournalStatus.APPROVED) -> MagicMock:
    j = MagicMock()
    j.journal_entry_id = uuid.uuid4()
    j.journal_number = "JE-TEST-001"
    j.status = status
    j.posting_batch_id = None
    j.approved_by_user_id = uuid.uuid4()
    j.approved_at = "stub-timestamp"
    return j


def _call_post_to_ledger(db: MagicMock, journal_entry_id: uuid.UUID):
    return BasePostingAdapter.post_to_ledger(
        db,
        organization_id=uuid.uuid4(),
        journal_entry_id=journal_entry_id,
        posting_date="2025-01-20",
        idempotency_key="test-key",
        source_module="BANKING",
        correlation_id="test-correlation",
        posted_by_user_id=uuid.uuid4(),
    )


@patch("app.services.finance.posting.base.LedgerPostingService.post_journal_entry")
def test_revert_to_draft_when_period_guard_raises(mock_post: MagicMock) -> None:
    """Period-closed HTTPException → journal reverted to DRAFT, approve fields cleared."""
    journal = _journal_stub()
    db = MagicMock()
    db.get.return_value = journal

    mock_post.side_effect = HTTPException(
        status_code=400, detail="Period 'January 2025' is permanently closed"
    )

    result = _call_post_to_ledger(db, journal.journal_entry_id)

    assert result.success is False
    assert "permanently closed" in result.message
    assert journal.status == JournalStatus.DRAFT
    assert journal.approved_by_user_id is None
    assert journal.approved_at is None
    db.flush.assert_called()


@patch("app.services.finance.posting.base.LedgerPostingService.post_journal_entry")
def test_revert_when_service_returns_success_false(mock_post: MagicMock) -> None:
    """Non-exception failure (success=False from service) also reverts."""
    journal = _journal_stub()
    db = MagicMock()
    db.get.return_value = journal

    mock_post.return_value = MagicMock(success=False, message="Validation failed")

    result = _call_post_to_ledger(db, journal.journal_entry_id)

    assert result.success is False
    assert journal.status == JournalStatus.DRAFT


@patch("app.services.finance.posting.base.LedgerPostingService.post_journal_entry")
def test_no_revert_when_journal_has_batch_id(mock_post: MagicMock) -> None:
    """Never touch a journal that already partially posted (has batch_id)."""
    journal = _journal_stub()
    journal.posting_batch_id = uuid.uuid4()  # already partially posted
    db = MagicMock()
    db.get.return_value = journal

    mock_post.side_effect = RuntimeError("downstream blew up")

    result = _call_post_to_ledger(db, journal.journal_entry_id)

    assert result.success is False
    assert journal.status == JournalStatus.APPROVED  # unchanged


@patch("app.services.finance.posting.base.LedgerPostingService.post_journal_entry")
def test_no_revert_when_journal_not_in_approved(mock_post: MagicMock) -> None:
    """Never touch a journal whose status is not APPROVED (defensive)."""
    journal = _journal_stub(status=JournalStatus.DRAFT)
    db = MagicMock()
    db.get.return_value = journal

    mock_post.side_effect = RuntimeError("boom")

    result = _call_post_to_ledger(db, journal.journal_entry_id)

    assert result.success is False
    assert journal.status == JournalStatus.DRAFT  # unchanged


@patch("app.services.finance.posting.base.LedgerPostingService.post_journal_entry")
def test_success_path_does_not_revert(mock_post: MagicMock) -> None:
    """Successful post leaves the journal alone (the service flips it to POSTED)."""
    journal = _journal_stub()
    db = MagicMock()
    db.get.return_value = journal

    batch_id = uuid.uuid4()
    mock_post.return_value = MagicMock(
        success=True, posting_batch_id=batch_id, message="ok"
    )

    result = _call_post_to_ledger(db, journal.journal_entry_id)

    assert result.success is True
    assert result.posting_batch_id == batch_id
    # The adapter never touches the journal on the success path.
    assert journal.status == JournalStatus.APPROVED  # unchanged by adapter
