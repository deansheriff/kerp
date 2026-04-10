"""
Sync specific ERPNext Payment Entry documents by name.

Useful when we need to backfill a small set of ACC-PAY entries without running a
full payment_entries sync.
"""

from __future__ import annotations

from uuid import UUID



ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
ADMIN_PERSON_ID = UUID("c8e5f2ee-4f9f-46d0-a6c7-22e4f717a58b")


def main() -> None:
    print("ERPNext API sync is disabled. Use SQL-based sync tooling.")  # noqa: T201
    raise SystemExit(2)


if __name__ == "__main__":
    main()
