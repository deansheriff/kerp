"""Tests for the Splynx detached-match backfill migration.

Only the note-parsing helper is unit-testable in isolation.  The full
upgrade() runs against a live PG instance via Alembic.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "20260515_backfill_splynx_match_junction.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location(
        "backfill_splynx_junction", _MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestExtractPaymentId:
    """``_extract_payment_id`` parses the Splynx note format."""

    def test_extracts_uuid_from_date_amount_note(self, migration) -> None:
        note = " [Matched to Splynx payment a1b2c3d4-e5f6-7890-abcd-ef0123456789 by date+amount]"
        parsed = migration._extract_payment_id(note)
        assert parsed == uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef0123456789")

    def test_extracts_uuid_from_customer_match_note(self, migration) -> None:
        note = (
            " [Matched to Splynx payment 12345678-1234-1234-1234-123456789012 "
            "by customer+date+amount]"
        )
        parsed = migration._extract_payment_id(note)
        assert parsed == uuid.UUID("12345678-1234-1234-1234-123456789012")

    def test_extracts_uuid_from_score_gap_note(self, migration) -> None:
        note = (
            "Some prior log entry\n"
            "[Matched to Splynx payment "
            "abcdef01-2345-6789-abcd-ef0123456789 "
            "by score-gap (score=92.0, gap=18.0)]"
        )
        parsed = migration._extract_payment_id(note)
        assert parsed == uuid.UUID("abcdef01-2345-6789-abcd-ef0123456789")

    def test_case_insensitive(self, migration) -> None:
        note = "Matched to Splynx payment ABCDEF01-2345-6789-ABCD-EF0123456789 by foo"
        parsed = migration._extract_payment_id(note)
        assert parsed == uuid.UUID("abcdef01-2345-6789-abcd-ef0123456789")

    def test_returns_none_for_no_match(self, migration) -> None:
        assert migration._extract_payment_id("regular note text") is None
        assert (
            migration._extract_payment_id("Matched to something else entirely") is None
        )

    def test_returns_none_for_none_input(self, migration) -> None:
        assert migration._extract_payment_id(None) is None

    def test_returns_none_for_empty_input(self, migration) -> None:
        assert migration._extract_payment_id("") is None

    def test_returns_none_for_malformed_uuid(self, migration) -> None:
        # Truncated UUID — regex won't match
        note = "Matched to Splynx payment a1b2c3d4 by date+amount"
        assert migration._extract_payment_id(note) is None

    def test_first_match_wins_for_multiple(self, migration) -> None:
        # If somehow two Splynx notes accumulated on one line (re-matching),
        # the first UUID wins.
        note = (
            "[Matched to Splynx payment 11111111-1111-1111-1111-111111111111 by foo]"
            "\n[Matched to Splynx payment 22222222-2222-2222-2222-222222222222 by bar]"
        )
        parsed = migration._extract_payment_id(note)
        assert parsed == uuid.UUID("11111111-1111-1111-1111-111111111111")
