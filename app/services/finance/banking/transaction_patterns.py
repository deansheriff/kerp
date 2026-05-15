"""Shared regex patterns for bank statement line classification.

These patterns are used by both the auto-reconciliation passes
(``auto_reconciliation_parts``) and the rule-based engine
(``reconciliation_engine_parts``).  They live here so that both engines see
the same pattern definitions — historically each engine maintained its own
copy and they would drift apart.
"""

from __future__ import annotations

import re

# Paystack transaction IDs: 12-14 hex characters. Used to recognise
# references in line description / reference / bank_reference fields.
PAYSTACK_REF_RE = re.compile(r"[0-9a-f]{12,14}", re.IGNORECASE)

# Pass 6 / BANK_FEE rule: Paystack processing fees on outbound lines.
BANK_FEE_RE = re.compile(r"Paystack Fee:", re.IGNORECASE)

# Pass 7: Settlement detection (inter-bank transfers from Paystack to org bank).
SETTLEMENT_RE = re.compile(r"Settlement( to bank)?:", re.IGNORECASE)

# Paystack-related deposit patterns on receiving banks.
# Matches both "Paystack payout" descriptions and PSST10-prefixed batch codes.
PAYSTACK_DEPOSIT_RE = re.compile(r"paystack|PSST10", re.IGNORECASE)

# Paystack OPEX account naming convention (used to detect expense-transfer
# accounts that route through Paystack).
PAYSTACK_OPEX_RE = re.compile(r"paystack.*opex|opex.*paystack", re.IGNORECASE)

# Dry-run contra-transfer suggestion pass: flag lines whose text suggests an
# inter-bank transfer that has no AR/AP source document.
CONTRA_TRANSFER_RE = re.compile(
    r"transfer|inter.?bank|xfer|trx\s*to|trx\s*from|trf",
    re.IGNORECASE,
)
