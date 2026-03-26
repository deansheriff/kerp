from __future__ import annotations

from unittest.mock import Mock

from app.models.finance.core_org.pfa_directory import PFADirectory
from app.services.people.payroll.pfa_directory import PFADirectoryService


def test_list_active_pfas_returns_directory_rows_when_present():
    db = Mock()
    row = PFADirectory(
        pfa_code="001",
        pfa_name="ARM Pension Managers Limited",
        short_name="ARM Pensions",
        aliases=["ARM"],
        is_active=True,
    )
    scalar_result = Mock()
    scalar_result.all.return_value = [row]
    db.scalars.return_value = scalar_result

    result = PFADirectoryService(db).list_active_pfas()

    assert result == [row]


def test_list_active_pfas_uses_seeded_fallback_when_directory_is_empty():
    db = Mock()
    scalar_result = Mock()
    scalar_result.all.return_value = []
    db.scalars.return_value = scalar_result

    result = PFADirectoryService(db).list_active_pfas()

    assert len(result) >= 23
    assert all(isinstance(pfa, PFADirectory) for pfa in result)
    assert all(pfa.is_active for pfa in result)
    assert any(pfa.pfa_code == "001" for pfa in result)
    assert any(pfa.pfa_code == "040" for pfa in result)
