"""
PFA directory lookup service.

Provides active Pension Fund Administrator options for web forms and exports.
Falls back to a built-in directory when the shared table is empty so critical
dropdowns do not render blank in partially seeded environments.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance.core_org.pfa_directory import PFADirectory

logger = logging.getLogger(__name__)

_DEFAULT_ACTIVE_PFAS: tuple[dict[str, str | list[str]], ...] = (
    {
        "pfa_code": "001",
        "pfa_name": "ARM Pension Managers Limited",
        "short_name": "ARM Pensions",
        "aliases": ["ARM", "ARM Pension"],
    },
    {
        "pfa_code": "002",
        "pfa_name": "Crusader Sterling Pensions Limited",
        "short_name": "Crusader Pensions",
        "aliases": ["Crusader", "Crusader Sterling"],
    },
    {
        "pfa_code": "003",
        "pfa_name": "First Guarantee Pension Limited",
        "short_name": "First Guarantee",
        "aliases": ["FGPL", "First Guarantee Pension"],
    },
    {
        "pfa_code": "004",
        "pfa_name": "FCMB Pensions Limited",
        "short_name": "FCMB Pensions",
        "aliases": ["FCMB Pension"],
    },
    {
        "pfa_code": "005",
        "pfa_name": "Fidelity Pension Managers Limited",
        "short_name": "Fidelity Pensions",
        "aliases": ["Fidelity Pension"],
    },
    {
        "pfa_code": "006",
        "pfa_name": "IEI-Anchor Pension Managers Limited",
        "short_name": "IEI-Anchor",
        "aliases": ["IEI Anchor", "Anchor Pensions"],
    },
    {
        "pfa_code": "007",
        "pfa_name": "Leadway Pensure PFA Limited",
        "short_name": "Leadway Pensure",
        "aliases": ["Leadway", "Pensure"],
    },
    {
        "pfa_code": "008",
        "pfa_name": "NLPC Pension Fund Administrators Limited",
        "short_name": "NLPC Pensions",
        "aliases": ["NLPC", "NLPC Pension"],
    },
    {
        "pfa_code": "009",
        "pfa_name": "NPF Pensions Limited",
        "short_name": "NPF Pensions",
        "aliases": ["NPF", "Nigerian Police Force Pension"],
    },
    {
        "pfa_code": "010",
        "pfa_name": "OAK Pensions Limited",
        "short_name": "OAK Pensions",
        "aliases": ["OAK", "Oak Pension"],
    },
    {
        "pfa_code": "011",
        "pfa_name": "Pensions Alliance Limited",
        "short_name": "PAL Pensions",
        "aliases": ["PAL", "Pensions Alliance"],
    },
    {
        "pfa_code": "012",
        "pfa_name": "Premium Pension Limited",
        "short_name": "Premium Pensions",
        "aliases": ["Premium", "Premium Pension"],
    },
    {
        "pfa_code": "013",
        "pfa_name": "Radix Pension Managers Limited",
        "short_name": "Radix Pensions",
        "aliases": ["Radix", "Radix Pension"],
    },
    {
        "pfa_code": "014",
        "pfa_name": "Sigma Pensions Limited",
        "short_name": "Sigma Pensions",
        "aliases": ["Sigma", "Sigma Pension"],
    },
    {
        "pfa_code": "015",
        "pfa_name": "Stanbic IBTC Pension Managers Limited",
        "short_name": "Stanbic IBTC Pensions",
        "aliases": ["Stanbic IBTC", "Stanbic Pension", "IBTC Pensions"],
    },
    {
        "pfa_code": "016",
        "pfa_name": "Tangerine APT Pensions Limited",
        "short_name": "Tangerine Pensions",
        "aliases": ["Tangerine", "APT Pensions", "Tangerine APT"],
    },
    {
        "pfa_code": "017",
        "pfa_name": "Trustfund Pensions Limited",
        "short_name": "Trustfund Pensions",
        "aliases": ["Trustfund", "Trust Fund Pension"],
    },
    {
        "pfa_code": "018",
        "pfa_name": "Veritas Glanvills Pensions Limited",
        "short_name": "Veritas Glanvills",
        "aliases": ["Veritas", "Glanvills", "VG Pensions"],
    },
    {
        "pfa_code": "019",
        "pfa_name": "Access Pensions Limited",
        "short_name": "Access Pensions",
        "aliases": ["Access Pension"],
    },
    {
        "pfa_code": "020",
        "pfa_name": "Nigerian University Pension Management Company",
        "short_name": "NUPEMCO",
        "aliases": ["NUPEMCO Pension"],
    },
    {
        "pfa_code": "021",
        "pfa_name": "Investment One Pension Managers Limited",
        "short_name": "Investment One",
        "aliases": ["Investment One Pension"],
    },
    {
        "pfa_code": "022",
        "pfa_name": "Norrenberger Pensions Limited",
        "short_name": "Norrenberger Pensions",
        "aliases": ["Norrenberger", "Norrenberger Pension"],
    },
    {
        "pfa_code": "040",
        "pfa_name": "GUARANTY TRUST PENSION MANAGERS",
        "short_name": "GT",
        "aliases": ["GT"],
    },
)


class PFADirectoryService:
    """Lookup service for active Pension Fund Administrators."""

    def __init__(self, db: Session):
        self.db = db

    def list_active_pfas(self) -> list[PFADirectory]:
        """Return active PFAs ordered by name, with a seeded fallback."""
        rows = list(
            self.db.scalars(
                select(PFADirectory)
                .where(PFADirectory.is_active.is_(True))
                .order_by(PFADirectory.pfa_name)
            ).all()
        )
        if rows:
            return rows

        logger.warning(
            "core_org.pfa_directory returned no active rows; using fallback PFA list"
        )
        return [
            PFADirectory(
                pfa_code=entry["pfa_code"],
                pfa_name=entry["pfa_name"],
                short_name=entry["short_name"],
                aliases=entry["aliases"],
                is_active=True,
            )
            for entry in _DEFAULT_ACTIVE_PFAS
        ]


def pfa_directory_service(db: Session) -> PFADirectoryService:
    """Create a PFADirectoryService instance."""
    return PFADirectoryService(db)
