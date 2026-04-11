from __future__ import annotations

from datetime import date
from uuid import UUID

# Represents automated/system-initiated actions in audit columns.
# Used as fallback when no real user ID is available (e.g. batch sync).
SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000000")

# Minimum date for Splynx financial document sync.
# Records older than this are skipped (pre-2026 data was imported via the
# ERPNext clean sweep migration and must not be duplicated by Splynx sync).
# NOTE: Splynx invoice API silently ignores date_from/date_to params, so
# this floor is enforced client-side after parsing each record's date.
SPLYNX_SYNC_MIN_DATE = date(2026, 1, 1)

# Sentinel UUID recorded in ExternalSync.local_entity_id for pre-2026
# records that are skipped.  This prevents _has_changed() from returning
# True every cycle (the column is NOT NULL, so we cannot use None).
_PRE_CUTOFF_SENTINEL = UUID("00000000-0000-0000-0000-000000000001")

# Default mapping from Splynx payment method name fragments to ERP
# bank account name fragments.  Override via constructor parameter.
DEFAULT_BANK_NAME_MAPPING: dict[str, str | None] = {
    "zenith 461": "zenith 461",
    "zenith 523": "zenith 523",
    "paystack": "paystack",
    "pay stack": "paystack",
    "uba": "uba 96",
    "flutterwave": "flutterwave",
    "flutter wave": "flutterwave",
    "fluterwave": "flutterwave",
    "dotmac usd": "zenith usd",
    "cash": None,  # Cash doesn't map to a bank account
}
