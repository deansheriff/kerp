"""Coach settings UI uses the same resolver and atomic writer as AI workflows."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.domain_settings import SettingDomain
from app.services.finance.settings_web import SettingsWebService
from app.services.settings_spec import list_specs


@pytest.mark.parametrize("value", ["", "configured-value"])
def test_context_contains_all_providers_and_masks_secrets(value):
    db = MagicMock()
    with patch("app.services.coach.insight_engine.InsightEngine") as factory:
        factory.return_value._setting.return_value = value
        result = SettingsWebService().get_coach_settings_context(db, uuid4())
    context = result["coach_settings"]
    assert set(context) == {s.key for s in list_specs(SettingDomain.coach)}
    assert "gemini_api_key" in context
    for key in ("gemini_api_key", "llama_api_key", "deepseek_api_key"):
        assert context[key]["value"] == ""
        assert context[key]["is_secret"]
        assert context[key]["has_value"] == bool(value)
    assert context["gemini_base_url"]["value"] == value
    assert context["timeout_seconds"]["min"] == 5
    assert context["timeout_seconds"]["max"] == 120
    assert context["max_retries"]["min"] == 0


@pytest.mark.parametrize("outcome", [(True, None), (False, "Invalid provider URL")])
def test_update_delegates_to_atomic_tenant_writer(outcome):
    db = MagicMock()
    org_id = uuid4()
    data = {"gemini_api_key": "new-key", "ai_enabled": "true"}
    with patch(
        "app.services.coach.configuration.save_configuration", return_value=outcome
    ) as save:
        assert SettingsWebService().update_coach_settings(db, org_id, data) == outcome
        save.assert_called_once_with(db, org_id, data)
    db.commit.assert_not_called()
