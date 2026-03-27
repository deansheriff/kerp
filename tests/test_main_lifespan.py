from unittest.mock import MagicMock, patch

import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_lifespan_registers_payroll_handlers(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(main_module, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(main_module, "validate_startup", lambda db, **_: True)
    monkeypatch.setattr(main_module, "seed_all_settings", lambda db: None)

    with patch(
        "app.services.people.payroll.event_handlers.register_payroll_handlers"
    ) as mock_register:
        async with main_module.lifespan(main_module.app):
            pass

    mock_register.assert_called_once_with()
    mock_db.close.assert_called_once_with()
