import uuid
from unittest.mock import Mock

import pytest

from app.models.finance.core_org.location import Location, LocationType
from app.services.people.hr.errors import ValidationError
from app.services.people.hr.organization import OrganizationService


def _location(
    organization_id: uuid.UUID,
    *,
    location_id: uuid.UUID | None = None,
    code: str = "LAG",
    name: str = "Lagos",
) -> Location:
    return Location(
        location_id=location_id or uuid.uuid4(),
        organization_id=organization_id,
        location_code=code,
        location_name=name,
        location_type=LocationType.BRANCH,
    )


def test_create_location_rejects_duplicate_code_before_insert():
    org_id = uuid.uuid4()
    db = Mock()
    db.scalar.return_value = _location(org_id, code="LAG")
    service = OrganizationService(db, org_id)

    with pytest.raises(ValidationError, match="already exists"):
        service.create_location(
            location_code="LAG",
            location_name="Lagos Annex",
            location_type=LocationType.BRANCH,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_update_location_rejects_duplicate_code_for_another_branch():
    org_id = uuid.uuid4()
    current = _location(org_id, code="ABJ")
    existing = _location(org_id, code="LAG")
    db = Mock()
    db.scalar.side_effect = [current, existing]
    service = OrganizationService(db, org_id)

    with pytest.raises(ValidationError, match="already exists"):
        service.update_location(current.location_id, {"location_code": "LAG"})

    db.flush.assert_not_called()


def test_update_location_flushes_changes_before_refresh():
    org_id = uuid.uuid4()
    current = _location(org_id, code="ABJ")
    db = Mock()
    db.scalar.side_effect = [current, None]
    service = OrganizationService(db, org_id)

    updated = service.update_location(
        current.location_id,
        {"location_code": " LAG2 ", "location_name": " Lagos 2 "},
    )

    assert updated is current
    assert current.location_code == "LAG2"
    assert current.location_name == "Lagos 2"
    db.flush.assert_called_once()
    db.refresh.assert_called_once_with(current)
